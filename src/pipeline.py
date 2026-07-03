import os
import sqlite3
import pandas as pd
import numpy as np

def clean_and_ingest(csv_filename="raw_ais_data.csv", db_filename="ships.db"):
    print("Starting AIS Data Pipeline...")
    
    if not os.path.exists(csv_filename):
        raise FileNotFoundError(f"Source raw data file '{csv_filename}' not found. Please run generator first.")
        
    # 1. Load the raw data
    print(f"Reading raw data from {csv_filename}...")
    df = pd.read_csv(csv_filename)
    initial_count = len(df)
    print(f"Loaded {initial_count} raw records.")
    
    # 2. Parse timestamps to uniform format
    print("Normalizing timestamps...")
    # Convert series to uniform datetime
    is_digit = df['timestamp'].astype(str).str.match(r'^\d+$')
    
    parsed_timestamps = pd.Series(pd.NaT, index=df.index, dtype='datetime64[ns, UTC]')
    
    # Parse epochs
    epoch_idx = df[is_digit].index
    if not epoch_idx.empty:
        parsed_timestamps.loc[epoch_idx] = pd.to_datetime(
            df.loc[epoch_idx, 'timestamp'].astype(float), 
            unit='s', 
            utc=True,
            errors='coerce'
        )
        
    # Parse date strings (ISO, DD/MM/YYYY, YYYY/MM/DD, etc.)
    str_idx = df[~is_digit].index
    if not str_idx.empty:
        parsed_timestamps.loc[str_idx] = pd.to_datetime(
            df.loc[str_idx, 'timestamp'], 
            utc=True,
            errors='coerce', 
            format='mixed'
        )
        
    df['parsed_time'] = parsed_timestamps
    
    # Drop rows with invalid timestamps
    invalid_time_count = df['parsed_time'].isna().sum()
    if invalid_time_count > 0:
        print(f"Dropping {invalid_time_count} records due to unparseable timestamps.")
        df = df.dropna(subset=['parsed_time'])
        
    # Format uniformly as 'YYYY-MM-DD HH:MM:SS' string
    df['timestamp'] = df['parsed_time'].dt.strftime('%Y-%m-%d %H:%M:%S')
    df = df.drop(columns=['parsed_time'])
    
    # 3. Clean coordinates and enforce geographic bounding box
    # Strait of Hormuz and Arabian Sea: Lat 12°N to 28°N, Lon 50°E to 65°E
    print("Verifying geographic bounding box (Lat 12°N-28°N, Lon 50°E-65°E)...")
    
    # Drop null coordinates first
    coord_nulls = df['latitude'].isna() | df['longitude'].isna()
    if coord_nulls.any():
        print(f"Dropping {coord_nulls.sum()} records with missing coordinates.")
        df = df[~coord_nulls]
        
    # Apply bounding box constraints
    in_bbox = (
        (df['latitude'] >= 12.0) & (df['latitude'] <= 28.0) &
        (df['longitude'] >= 50.0) & (df['longitude'] <= 65.0)
    )
    out_bbox_count = (~in_bbox).sum()
    if out_bbox_count > 0:
        print(f"Dropping {out_bbox_count} out-of-bounds records.")
        df = df[in_bbox]
        
    # 4. Remove duplicates
    # Remove exact duplicate rows
    row_dupes = df.duplicated().sum()
    if row_dupes > 0:
        print(f"Removing {row_dupes} identical duplicate rows.")
        df = df.drop_duplicates()
        
    # Remove duplicate positions for same ship (mmsi) at the same timestamp
    mmsi_time_dupes = df.duplicated(subset=['mmsi', 'timestamp']).sum()
    if mmsi_time_dupes > 0:
        print(f"Removing {mmsi_time_dupes} duplicate MMSI + Timestamp records.")
        df = df.drop_duplicates(subset=['mmsi', 'timestamp'], keep='first')
        
    # 5. Categorize ships
    # AIS Standard type codes: 30 is Fishing, 70-79 Cargo, 80-89 Tanker
    print("Categorizing ships...")
    
    def map_ship_type(code):
        try:
            code_val = int(code)
            if code_val == 30:
                return 'Fishing'
            elif 70 <= code_val <= 79:
                return 'Cargo'
            elif 80 <= code_val <= 89:
                return 'Tanker'
            else:
                return 'Other'
        except (ValueError, TypeError):
            return 'Other'
            
    df['ship_category'] = df['ship_type_code'].apply(map_ship_type)
    
    # Drop the raw code if we want clean tables (or keep it for reference, let's keep it but rename/ensure structure)
    cleaned_df = df[[
        'mmsi', 
        'ship_name', 
        'ship_category', 
        'latitude', 
        'longitude', 
        'sog', 
        'cog', 
        'heading', 
        'timestamp'
    ]].copy()
    
    final_count = len(cleaned_df)
    dropped_total = initial_count - final_count
    print(f"Cleaned data results: {final_count} / {initial_count} records retained ({dropped_total} filtered).")
    
    # Print categorization report
    category_summary = cleaned_df['ship_category'].value_counts()
    print("Ship Category Summary:")
    for cat, count in category_summary.items():
        print(f" - {cat}: {count}")
        
    # 6. Save to SQLite database
    print(f"Saving cleaned data to SQLite database '{db_filename}'...")
    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()
    
    # Create the table schema explicitly
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ais_tracking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mmsi INTEGER NOT NULL,
        ship_name TEXT,
        ship_category TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        sog REAL,
        cog REAL,
        heading INTEGER,
        timestamp TEXT NOT NULL,
        UNIQUE(mmsi, timestamp) ON CONFLICT REPLACE
    );
    """)
    conn.commit()
    
    # Save the cleaned DataFrame using pandas to_sql
    # Since we have UNIQUE constraint on mmsi+timestamp and auto-increment ID,
    # let's write to a temp table and insert or replace to avoid duplicates if re-run.
    cleaned_df.to_sql('ais_tracking_temp', conn, if_exists='replace', index=False)
    
    cursor.execute("""
    INSERT OR REPLACE INTO ais_tracking (mmsi, ship_name, ship_category, latitude, longitude, sog, cog, heading, timestamp)
    SELECT mmsi, ship_name, ship_category, latitude, longitude, sog, cog, heading, timestamp
    FROM ais_tracking_temp;
    """)
    cursor.execute("DROP TABLE ais_tracking_temp;")
    conn.commit()
    
    # Verify the table size
    cursor.execute("SELECT COUNT(*) FROM ais_tracking;")
    db_count = cursor.fetchone()[0]
    conn.close()
    
    print(f"Successfully loaded data. Database 'ais_tracking' table now has {db_count} records.")
    print("Pipeline Execution Completed.")

if __name__ == "__main__":
    clean_and_ingest()
