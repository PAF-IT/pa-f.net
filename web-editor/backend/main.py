#!/usr/bin/env python3
"""
Simple FastAPI backend for PAF site editor.
"""

import json
import os
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# Add the parent directory to the path so we can import palimpsest
sys.path.append(str(Path(__file__).parent.parent.parent))

from palimpsest import StaticSiteGenerator

app = FastAPI(title="PAF Site Editor API", version="1.0.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Path to the sitemap.json file (relative to the project root)
SITEMAP_PATH = Path(__file__).parent.parent.parent / "sitemap.json"
STATIC_OUTPUT_DIR = Path(__file__).parent.parent.parent / "paf-static"


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "PAF Site Editor API is running"}


@app.get("/api/sitemap")
async def get_sitemap():
    """Get the current sitemap data."""
    try:
        if not SITEMAP_PATH.exists():
            raise HTTPException(status_code=404, detail="Sitemap file not found")
        
        with open(SITEMAP_PATH, 'r', encoding='utf-8') as f:
            sitemap_data = json.load(f)
        
        return sitemap_data
    
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON in sitemap file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading sitemap: {str(e)}")


@app.post("/api/sitemap")
async def update_sitemap(sitemap_data: dict):
    """Update the sitemap and regenerate the static site."""
    try:
        # Validate that we have a valid sitemap structure
        if not isinstance(sitemap_data, dict):
            raise HTTPException(status_code=400, detail="Sitemap must be a dictionary")
        
        # Basic validation of sitemap structure
        for path, page_data in sitemap_data.items():
            if not isinstance(page_data, dict):
                raise HTTPException(status_code=400, detail=f"Invalid page data for {path}")
            
            required_fields = ['title', 'md']
            for field in required_fields:
                if field not in page_data:
                    raise HTTPException(status_code=400, detail=f"Missing required field '{field}' for page {path}")
        
        # Save the updated sitemap
        with open(SITEMAP_PATH, 'w', encoding='utf-8') as f:
            json.dump(sitemap_data, f, indent=2, ensure_ascii=False)
        
        # Regenerate the static site
        generator = StaticSiteGenerator(
            sitemap_data=sitemap_data, 
            output_dir=str(STATIC_OUTPUT_DIR)
        )
        generator.generate_site()
        
        return {"message": "Sitemap updated and static site regenerated successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating sitemap: {str(e)}")


@app.get("/api/status")
async def get_status():
    """Get the current status of the system."""
    try:
        sitemap_exists = SITEMAP_PATH.exists()
        static_dir_exists = STATIC_OUTPUT_DIR.exists()
        
        sitemap_size = 0
        if sitemap_exists:
            with open(SITEMAP_PATH, 'r', encoding='utf-8') as f:
                sitemap_data = json.load(f)
                sitemap_size = len(sitemap_data)
        
        return {
            "sitemap_exists": sitemap_exists,
            "sitemap_path": str(SITEMAP_PATH),
            "sitemap_size": sitemap_size,
            "static_dir_exists": static_dir_exists,
            "static_dir_path": str(STATIC_OUTPUT_DIR)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")


if __name__ == "__main__":
    print(f"Starting PAF Site Editor API...")
    print(f"Sitemap path: {SITEMAP_PATH}")
    print(f"Static output directory: {STATIC_OUTPUT_DIR}")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
