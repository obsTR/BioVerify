#!/usr/bin/env python
"""Smoke test script to verify end-to-end functionality."""
import requests
import time
import sys
from pathlib import Path

API_BASE_URL = "http://localhost:8000"
AUTH_TOKEN = "dev-token"

def create_test_video():
    """Create a simple test video file."""
    import cv2
    import numpy as np
    
    test_video_path = Path("sample_test.mp4")
    if test_video_path.exists():
        return str(test_video_path)
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(test_video_path), fourcc, 30.0, (128, 128))
    
    for i in range(90):
        frame = np.zeros((128, 128, 3), dtype=np.uint8)
        cv2.putText(frame, f"Frame {i}", (10, 64),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        out.write(frame)
    
    out.release()
    return str(test_video_path)


def main():
    print("BioVerify Smoke Test")
    print("=" * 50)
    
    # Create test video
    print("\n1. Creating test video...")
    video_path = create_test_video()
    print(f"   Created: {video_path}")
    
    # Upload video
    print("\n2. Uploading video to API...")
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    with open(video_path, 'rb') as f:
        files = {'video': ('test.mp4', f, 'video/mp4')}
        response = requests.post(
            f"{API_BASE_URL}/analyses",
            files=files,
            headers=headers,
        )
    
    if response.status_code != 200:
        print(f"   ERROR: Upload failed: {response.status_code}")
        print(f"   Response: {response.text}")
        sys.exit(1)
    
    data = response.json()
    analysis_id = data['analysis_id']
    print(f"   Analysis ID: {analysis_id}")
    print(f"   Status: {data['status']}")
    
    # Poll for completion
    print("\n3. Polling for analysis completion...")
    max_wait = 300  # 5 minutes
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        response = requests.get(
            f"{API_BASE_URL}/analyses/{analysis_id}",
            headers=headers,
        )
        
        if response.status_code != 200:
            print(f"   ERROR: Status check failed: {response.status_code}")
            sys.exit(1)
        
        data = response.json()
        status = data['status']
        print(f"   Status: {status}")
        
        if status == 'done':
            print("\n4. Analysis completed!")
            result = data.get('result_json', {})
            print(f"   Verdict: {result.get('verdict', 'N/A')}")
            print(f"   Score: {result.get('score', 'N/A')}")
            print(f"   Confidence: {result.get('confidence', 'N/A')}")
            
            # Get evidence
            print("\n5. Fetching evidence index...")
            evidence_response = requests.get(
                f"{API_BASE_URL}/analyses/{analysis_id}/evidence",
                headers=headers,
            )
            if evidence_response.status_code == 200:
                evidence = evidence_response.json()
                print(f"   Evidence artifacts: {len(evidence.get('signed_urls', {}))}")
                print("   ✓ Smoke test passed!")
                sys.exit(0)
            else:
                print(f"   Warning: Could not fetch evidence: {evidence_response.status_code}")
                sys.exit(0)
        
        elif status == 'failed':
            print("\n   ERROR: Analysis failed")
            print(f"   Error: {data.get('error_message', 'Unknown error')}")
            sys.exit(1)
        
        time.sleep(2)
    
    print("\n   ERROR: Analysis timed out")
    sys.exit(1)


if __name__ == "__main__":
    main()
