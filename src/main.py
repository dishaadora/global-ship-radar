import os
import sqlite3
# pyrefly: ignore [missing-import]
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(
    title="Maritime Radar Tracking API",
    description="Backend API serving AIS ship tracking data in the Strait of Hormuz & Arabian Sea.",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "ships.db")

def get_db_connection():
    if not os.path.exists(DB_PATH):
        raise HTTPException(
            status_code=500, 
            detail=f"Database file not found at {DB_PATH}. Please run the pipeline script first."
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/")
def read_root():
    """
    Serves the frontend dashboard index.html at the root URL.
    """
    index_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Maritime Radar Tracking System API is running."}

@app.get("/api/ships")
def get_active_ships(
    type: Optional[str] = Query(None, description="Filter by ship category ('Cargo', 'Tanker', 'Fishing', 'Other')"),
    mmsi: Optional[int] = Query(None, description="Filter by unique Maritime Mobile Service Identity")
):
    """
    Returns current location and details of all active ships.
    An active ship is defined by its latest reported position in the database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Base query using JOIN to get only the latest report for each unique mmsi
    query = """
        SELECT t1.mmsi, t1.ship_name, t1.ship_category, t1.latitude, t1.longitude, t1.sog, t1.cog, t1.heading, t1.timestamp
        FROM ais_tracking t1
        JOIN (
            SELECT mmsi, MAX(timestamp) as max_ts
            FROM ais_tracking
            GROUP BY mmsi
        ) t2 ON t1.mmsi = t2.mmsi AND t1.timestamp = t2.max_ts
        WHERE 1=1
    """
    params = []
    
    if mmsi is not None:
        query += " AND t1.mmsi = ?"
        params.append(mmsi)
        
    if type is not None:
        query += " AND LOWER(t1.ship_category) = LOWER(?)"
        params.append(type)
        
    query += " ORDER BY t1.ship_name ASC"
    
    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
        result = [dict(row) for row in rows]
        return result
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")
    finally:
        conn.close()

@app.get("/api/ships/history")
def get_ship_history(
    mmsi: int = Query(..., description="MMSI of the ship to retrieve history for")
):
    """
    Returns the recent track/historical coordinates for a specific ship ordered chronologically.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT latitude, longitude, timestamp, sog, cog, heading
        FROM ais_tracking
        WHERE mmsi = ?
        ORDER BY timestamp ASC
    """
    
    try:
        cursor.execute(query, (mmsi,))
        rows = cursor.fetchall()
        
        if not rows:
            # Check if ship even exists in the database
            cursor.execute("SELECT COUNT(*) FROM ais_tracking WHERE mmsi = ?", (mmsi,))
            exists = cursor.fetchone()[0] > 0
            if not exists:
                raise HTTPException(status_code=404, detail=f"Ship with MMSI {mmsi} not found.")
            return []
            
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")
    finally:
        conn.close()

@app.get("/api/dashboard/stats")
def get_dashboard_stats():
    """
    Returns aggregated statistics (vessel count by type, average speeds, density metrics) for charts.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Vessel count by type (based on unique active vessels)
        vessel_counts_query = """
            SELECT ship_category, COUNT(DISTINCT mmsi) as count
            FROM ais_tracking
            GROUP BY ship_category
        """
        cursor.execute(vessel_counts_query)
        vessel_counts = {row['ship_category']: row['count'] for row in cursor.fetchall()}
        
        # 2. Average speed by ship type
        avg_speed_query = """
            SELECT ship_category, ROUND(AVG(sog), 2) as avg_speed
            FROM ais_tracking
            WHERE sog IS NOT NULL
            GROUP BY ship_category
        """
        cursor.execute(avg_speed_query)
        avg_speeds = {row['ship_category']: row['avg_speed'] for row in cursor.fetchall()}
        
        # 3. Overall stats
        overall_query = """
            SELECT COUNT(DISTINCT mmsi) as unique_ships, ROUND(AVG(sog), 2) as avg_sog_all
            FROM ais_tracking
        """
        cursor.execute(overall_query)
        overall_row = cursor.fetchone()
        
        # 4. Density metrics (vessel counts in 2x2 degree lat/lon grids based on active positions)
        density_query = """
            SELECT 
                CAST(latitude / 2.0 AS INTEGER) * 2 as lat_grid,
                CAST(longitude / 2.0 AS INTEGER) * 2 as lon_grid,
                COUNT(*) as vessel_count
            FROM ais_tracking t1
            JOIN (
                SELECT mmsi, MAX(timestamp) as max_ts
                FROM ais_tracking
                GROUP BY mmsi
            ) t2 ON t1.mmsi = t2.mmsi AND t1.timestamp = t2.max_ts
            GROUP BY lat_grid, lon_grid
        """
        cursor.execute(density_query)
        density_grid = [
            {
                "lat_min": row['lat_grid'],
                "lat_max": row['lat_grid'] + 2,
                "lon_min": row['lon_grid'],
                "lon_max": row['lon_grid'] + 2,
                "count": row['vessel_count']
            }
            for row in cursor.fetchall()
        ]
        
        # 5. Traffic trends over time (10-minute report volume)
        traffic_trend_query = """
            SELECT 
                strftime('%Y-%m-%d %H:', timestamp) || (CAST(strftime('%M', timestamp) / 10 AS INTEGER) * 10) || ':00' as time_label,
                COUNT(*) as report_count
            FROM ais_tracking
            GROUP BY time_label
            ORDER BY time_label ASC
        """
        cursor.execute(traffic_trend_query)
        traffic_trend = [
            {"time": row['time_label'], "count": row['report_count']}
            for row in cursor.fetchall()
        ]
        
        return {
            "total_active_ships": overall_row['unique_ships'],
            "average_speed_overall": overall_row['avg_sog_all'],
            "vessel_count_by_type": vessel_counts,
            "avg_speed_by_type": avg_speeds,
            "density_grid": density_grid,
            "traffic_trend": traffic_trend
        }
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database aggregation failed: {str(e)}")
    finally:
        conn.close()
