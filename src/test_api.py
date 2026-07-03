import os
import sys
# pyrefly: ignore [missing-import]
from fastapi.testclient import TestClient

# Ensure src is in the import path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.main import app

client = TestClient(app)

def run_tests():
    print("Starting API integration tests using TestClient...")
    
    # 1. Test root endpoint
    response = client.get("/")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    print("PASS: Root '/' endpoint matches expected status 200.")
    
    # 2. Test /api/ships
    response = client.get("/api/ships")
    assert response.status_code == 200
    ships = response.json()
    assert isinstance(ships, list)
    print(f"PASS: '/api/ships' returns list of {len(ships)} active ships.")
    
    # 3. Test /api/ships filtering by type
    response = client.get("/api/ships?type=Tanker")
    assert response.status_code == 200
    tankers = response.json()
    assert all(ship['ship_category'] == 'Tanker' for ship in tankers)
    print(f"PASS: '/api/ships?type=Tanker' successfully filtered to {len(tankers)} tankers.")
    
    # 4. Test /api/ships filtering by MMSI
    sample_mmsi = ships[0]['mmsi'] if ships else 311000123
    response = client.get(f"/api/ships?mmsi={sample_mmsi}")
    assert response.status_code == 200
    filtered_ships = response.json()
    assert len(filtered_ships) == 1
    assert filtered_ships[0]['mmsi'] == sample_mmsi
    print(f"PASS: '/api/ships?mmsi={sample_mmsi}' successfully returned exact vessel.")
    
    # 5. Test /api/ships/history
    response = client.get(f"/api/ships/history?mmsi={sample_mmsi}")
    assert response.status_code == 200
    history = response.json()
    assert isinstance(history, list)
    # Ensure sorted chronologically
    timestamps = [h['timestamp'] for h in history]
    assert timestamps == sorted(timestamps), "History is not sorted chronologically!"
    print(f"PASS: '/api/ships/history?mmsi={sample_mmsi}' returned {len(history)} chronologically sorted positions.")
    
    # 6. Test /api/ships/history with invalid MMSI
    response = client.get("/api/ships/history?mmsi=999999999")
    assert response.status_code == 404
    print("PASS: '/api/ships/history' with non-existent MMSI correctly returns 404.")
    
    # 7. Test /api/dashboard/stats
    response = client.get("/api/dashboard/stats")
    assert response.status_code == 200
    stats = response.json()
    assert "total_active_ships" in stats
    assert "average_speed_overall" in stats
    assert "vessel_count_by_type" in stats
    assert "avg_speed_by_type" in stats
    assert "density_grid" in stats
    assert "traffic_trend" in stats
    
    print("PASS: '/api/dashboard/stats' returned all expected aggregated statistics keys.")
    print("\nAPI Integration Tests Passed Successfully!")

if __name__ == "__main__":
    run_tests()
