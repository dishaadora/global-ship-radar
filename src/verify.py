import sqlite3
import re

def verify_pipeline(db_filename="ships.db"):
    print("Starting verification checks on the database...")
    
    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()
    
    # 1. Total records check
    cursor.execute("SELECT COUNT(*) FROM ais_tracking;")
    total_records = cursor.fetchone()[0]
    print(f"Total records in database: {total_records}")
    
    if total_records == 0:
        print("FAIL: No records found in the database.")
        conn.close()
        return False
        
    # 2. Bounding Box verification
    cursor.execute("""
    SELECT COUNT(*) FROM ais_tracking 
    WHERE latitude < 12.0 OR latitude > 28.0 
       OR longitude < 50.0 OR longitude > 65.0;
    """)
    out_of_bounds_count = cursor.fetchone()[0]
    if out_of_bounds_count > 0:
        print(f"FAIL: Found {out_of_bounds_count} records outside geographic bounds (Lat 12-28, Lon 50-65).")
    else:
        print("PASS: All records are within geographical boundaries.")
        
    # 3. Duplicate check (MMSI + Timestamp uniqueness)
    cursor.execute("""
    SELECT mmsi, timestamp, COUNT(*) as cnt 
    FROM ais_tracking 
    GROUP BY mmsi, timestamp 
    HAVING cnt > 1;
    """)
    duplicates = cursor.fetchall()
    if len(duplicates) > 0:
        print(f"FAIL: Found {len(duplicates)} duplicate MMSI+Timestamp pairs.")
    else:
        print("PASS: No duplicate MMSI+Timestamp pairs found.")
        
    # 4. Timestamp format verification (YYYY-MM-DD HH:MM:SS)
    cursor.execute("SELECT timestamp FROM ais_tracking;")
    timestamps = [row[0] for row in cursor.fetchall()]
    
    pattern = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')
    invalid_timestamps = [ts for ts in timestamps if not pattern.match(ts)]
    
    if len(invalid_timestamps) > 0:
        print(f"FAIL: Found {len(invalid_timestamps)} records with invalid timestamp format.")
        print(f"Sample invalid timestamps: {invalid_timestamps[:5]}")
    else:
        print("PASS: All timestamps match the uniform format 'YYYY-MM-DD HH:MM:SS'.")
        
    # 5. Ship Categorization verification
    cursor.execute("SELECT DISTINCT ship_category FROM ais_tracking;")
    categories = [row[0] for row in cursor.fetchall()]
    print(f"Unique ship categories in database: {categories}")
    
    invalid_categories = [cat for cat in categories if cat not in ['Cargo', 'Tanker', 'Fishing', 'Other']]
    if len(invalid_categories) > 0:
        print(f"FAIL: Found unexpected ship categories: {invalid_categories}")
    else:
        print("PASS: All ship categories are valid.")
        
    # Print sample data
    print("\nSample records from the database:")
    cursor.execute("SELECT mmsi, ship_name, ship_category, latitude, longitude, timestamp FROM ais_tracking LIMIT 5;")
    for row in cursor.fetchall():
        print(f"  MMSI: {row[0]}, Name: {row[1]:<16}, Cat: {row[2]:<8}, Lat: {row[3]:.4f}, Lon: {row[4]:.4f}, Time: {row[5]}")
        
    conn.close()
    
    # Return overall status
    success = (out_of_bounds_count == 0) and (len(duplicates) == 0) and (len(invalid_timestamps) == 0) and (len(invalid_categories) == 0)
    if success:
        print("\nAll integrity verification tests passed successfully!")
    else:
        print("\nSome verification checks failed. Check the errors above.")
    return success

if __name__ == "__main__":
    verify_pipeline()
