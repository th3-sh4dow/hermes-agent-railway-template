#!/usr/bin/env python3
"""
Supabase Storage Manager for Hermes Agent

This module handles automatic file offloading to Supabase Storage to prevent
Railway's 500MB volume limit from being exceeded. It monitors the /data directory
and uploads large files to Supabase, keeping local storage minimal.
"""

import os
import sys
import time
import shutil
import logging
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime

try:
    from supabase import create_client, Client
except ImportError:
    print("ERROR: supabase package not installed. Run: pip install supabase>=2.0.0")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SupabaseStorageManager:
    """Manages file uploads to Supabase Storage and local cleanup."""
    
    def __init__(self):
        """Initialize Supabase client from environment variables."""
        self.supabase_url = os.environ.get("SUPABASE_URL")
        self.supabase_key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SECRET_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError(
                "Missing Supabase credentials. Set SUPABASE_URL and SUPABASE_KEY "
                "environment variables."
            )
        
        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        self.bucket_name = os.environ.get("SUPABASE_BUCKET", "hermes-data")
        self.data_root = Path(os.environ.get("HERMES_HOME", "/data/.hermes"))
        self.size_threshold_mb = float(os.environ.get("STORAGE_THRESHOLD_MB", "10"))
        self.total_size_threshold_mb = float(os.environ.get("STORAGE_TOTAL_THRESHOLD_MB", "400"))
        
        logger.info(f"Initialized SupabaseStorageManager")
        logger.info(f"  Bucket: {self.bucket_name}")
        logger.info(f"  Data root: {self.data_root}")
        logger.info(f"  File threshold: {self.size_threshold_mb}MB")
        logger.info(f"  Total threshold: {self.total_size_threshold_mb}MB")
    
    def ensure_bucket_exists(self) -> bool:
        """Ensure the storage bucket exists in Supabase."""
        try:
            # Try to get bucket info
            buckets = self.client.storage.list_buckets()
            bucket_names = [b['name'] for b in buckets]
            
            if self.bucket_name not in bucket_names:
                logger.info(f"Creating bucket: {self.bucket_name}")
                self.client.storage.create_bucket(
                    self.bucket_name,
                    options={"public": False}
                )
                logger.info(f"Bucket '{self.bucket_name}' created successfully")
            else:
                logger.info(f"Bucket '{self.bucket_name}' already exists")
            return True
        except Exception as e:
            logger.error(f"Failed to ensure bucket exists: {e}")
            return False
    
    def get_directory_size(self, path: Path) -> int:
        """Calculate total size of directory in bytes."""
        total = 0
        try:
            for entry in path.rglob('*'):
                if entry.is_file():
                    try:
                        total += entry.stat().st_size
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError) as e:
            logger.warning(f"Error calculating directory size for {path}: {e}")
        return total
    
    def upload_file(self, local_path: Path, remote_path: Optional[str] = None) -> bool:
        """
        Upload a file to Supabase Storage.
        
        Args:
            local_path: Local file path to upload
            remote_path: Remote path in bucket (defaults to relative path from data_root)
        
        Returns:
            True if upload successful, False otherwise
        """
        try:
            if not local_path.exists() or not local_path.is_file():
                logger.warning(f"File does not exist or is not a file: {local_path}")
                return False
            
            # Generate remote path if not provided
            if remote_path is None:
                try:
                    remote_path = str(local_path.relative_to(self.data_root))
                except ValueError:
                    # File is outside data_root, use absolute path
                    remote_path = str(local_path.absolute()).replace(':', '_').replace('\\', '/')
            
            # Ensure remote path uses forward slashes
            remote_path = remote_path.replace('\\', '/')
            
            file_size_mb = local_path.stat().st_size / (1024 * 1024)
            logger.info(f"Uploading {local_path} ({file_size_mb:.2f}MB) to {remote_path}")
            
            with open(local_path, 'rb') as f:
                response = self.client.storage.from_(self.bucket_name).upload(
                    file=f,
                    path=remote_path,
                    file_options={"x-upsert": "true"}  # Overwrite if exists
                )
            
            logger.info(f"Successfully uploaded {remote_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to upload {local_path}: {e}")
            return False
    
    def delete_local_file(self, local_path: Path) -> bool:
        """
        Delete a local file after successful upload.
        
        Args:
            local_path: Path to local file to delete
        
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            if local_path.exists():
                local_path.unlink()
                logger.info(f"Deleted local file: {local_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete {local_path}: {e}")
            return False
    
    def find_large_files(self) -> List[Tuple[Path, float]]:
        """
        Find files larger than the size threshold.
        
        Returns:
            List of (path, size_in_mb) tuples
        """
        large_files = []
        
        if not self.data_root.exists():
            logger.warning(f"Data root does not exist: {self.data_root}")
            return large_files
        
        try:
            for file_path in self.data_root.rglob('*'):
                if file_path.is_file():
                    try:
                        size_bytes = file_path.stat().st_size
                        size_mb = size_bytes / (1024 * 1024)
                        
                        if size_mb >= self.size_threshold_mb:
                            large_files.append((file_path, size_mb))
                    except (OSError, PermissionError):
                        pass
        except Exception as e:
            logger.error(f"Error scanning for large files: {e}")
        
        # Sort by size descending
        large_files.sort(key=lambda x: x[1], reverse=True)
        return large_files
    
    def cleanup_large_files(self) -> int:
        """
        Find and upload large files to Supabase, then delete them locally.
        
        Returns:
            Number of files successfully processed
        """
        large_files = self.find_large_files()
        
        if not large_files:
            logger.info("No large files found to upload")
            return 0
        
        logger.info(f"Found {len(large_files)} large files to process")
        processed = 0
        
        for file_path, size_mb in large_files:
            logger.info(f"Processing: {file_path} ({size_mb:.2f}MB)")
            
            if self.upload_file(file_path):
                if self.delete_local_file(file_path):
                    processed += 1
            
            # Small delay to avoid overwhelming the API
            time.sleep(0.5)
        
        logger.info(f"Processed {processed}/{len(large_files)} files")
        return processed
    
    def check_total_size_and_cleanup(self) -> bool:
        """
        Check total data directory size and cleanup if needed.
        
        Returns:
            True if cleanup was performed, False otherwise
        """
        total_size_bytes = self.get_directory_size(self.data_root)
        total_size_mb = total_size_bytes / (1024 * 1024)
        
        logger.info(f"Total data directory size: {total_size_mb:.2f}MB / {self.total_size_threshold_mb}MB")
        
        if total_size_mb >= self.total_size_threshold_mb:
            logger.warning(f"Total size threshold exceeded! Starting cleanup...")
            self.cleanup_large_files()
            return True
        
        return False
    
    def run_monitoring_loop(self, check_interval_seconds: int = 300):
        """
        Run continuous monitoring loop to check storage and cleanup as needed.
        
        Args:
            check_interval_seconds: How often to check storage (default: 5 minutes)
        """
        logger.info(f"Starting storage monitoring loop (check interval: {check_interval_seconds}s)")
        
        # Ensure bucket exists on startup
        self.ensure_bucket_exists()
        
        while True:
            try:
                self.check_total_size_and_cleanup()
                time.sleep(check_interval_seconds)
            except KeyboardInterrupt:
                logger.info("Monitoring loop interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(60)  # Wait a minute before retrying


def main():
    """Main entry point for the storage manager."""
    try:
        manager = SupabaseStorageManager()
        
        # Check if running in monitoring mode
        if len(sys.argv) > 1 and sys.argv[1] == "monitor":
            # Run continuous monitoring
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 300
            manager.run_monitoring_loop(interval)
        else:
            # Run one-time cleanup
            manager.ensure_bucket_exists()
            manager.check_total_size_and_cleanup()
    
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
