#!/usr/bin/env python
"""
Time Capsule Data Migration Script

This script migrates data from JSON files to the SQLAlchemy database.
Run this script once after updating to the database-based implementation.
"""

import os
import json
import asyncio
import logging
import datetime
import uuid as uuid_lib
from db import init_db, async_session, UserDB, DiaryDB
import sqlite3

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get application directory
app_dir = os.path.dirname(os.path.abspath(__file__))
data_folder = os.path.join(app_dir, 'data')

# Path to users JSON file
users_file = os.path.join(data_folder, 'users.json')

async def migrate_users():
    """Migrate user data from JSON file to database."""
    logger.info("Starting user migration...")
    
    if not os.path.exists(users_file):
        logger.info("No users file found. Nothing to migrate.")
        return
    
    try:
        # Load existing users from file
        with open(users_file, 'r') as f:
            users_data = json.load(f)
        
        if not users_data:
            logger.info("No users found in JSON file. Nothing to migrate.")
            return
        
        # Create users in database
        async with async_session() as session:
            migrated_count = 0
            for uuid, data in users_data.items():
                # Check if user already exists
                user = await UserDB.get_user_by_uuid(session, uuid)
                if user:
                    logger.info(f"User {uuid} already exists in database. Skipping.")
                    continue
                
                # Create user
                name = data.get('name')
                age = data.get('age')
                is_reset = data.get('is_reset', False)
                
                user = await UserDB.create_user(session, uuid, name, age)
                
                # Set reset status if needed
                if is_reset:
                    reset_at = data.get('reset_at')
                    if reset_at:
                        # Convert string to datetime
                        try:
                            reset_datetime = datetime.datetime.fromisoformat(reset_at.replace('Z', '+00:00'))
                            user.reset_at = reset_datetime
                        except ValueError:
                            # If parsing fails, use current time
                            user.reset_at = datetime.datetime.utcnow()
                    else:
                        user.reset_at = datetime.datetime.utcnow()
                    
                    user.is_reset = True
                    await session.commit()
                
                migrated_count += 1
            
            logger.info(f"User migration completed. Migrated {migrated_count} users.")
    except Exception as e:
        logger.error(f"Error migrating users: {str(e)}", exc_info=True)
        raise

async def migrate_diary_entries():
    """Migrate diary entries from JSON files to database."""
    logger.info("Starting diary entries migration...")
    
    try:
        # Get all diary files
        diary_files = [f for f in os.listdir(data_folder) if f.startswith('diary_') and f.endswith('.json')]
        
        if not diary_files:
            logger.info("No diary files found. Nothing to migrate.")
            return
        
        migrated_count = 0
        async with async_session() as session:
            for file_name in diary_files:
                # Extract UUID from filename
                user_uuid = file_name.replace('diary_', '').replace('.json', '')
                
                # Check if user exists
                user = await UserDB.get_user_by_uuid(session, user_uuid)
                if not user:
                    logger.warning(f"User {user_uuid} not found in database. Creating user before migrating diary.")
                    user = await UserDB.create_user(session, user_uuid)
                
                # Load diary entries
                file_path = os.path.join(data_folder, file_name)
                with open(file_path, 'r') as f:
                    entries_data = json.load(f)
                
                if not entries_data:
                    logger.info(f"No entries found in {file_name}. Skipping.")
                    continue
                
                # Migrate each entry
                for entry in entries_data:
                    entry_id = entry.get('id')
                    
                    # Check if entry already exists
                    existing_entry = await DiaryDB.get_entry_by_uuid(session, entry_id)
                    if existing_entry:
                        logger.info(f"Entry {entry_id} already exists in database. Skipping.")
                        continue
                    
                    # Create entry
                    await DiaryDB.create_entry(
                        session,
                        user_uuid,
                        entry_id,
                        entry.get('title'),
                        entry.get('content'),
                        entry.get('date'),
                        entry.get('mood', 'calm'),
                        entry.get('pinned', False)
                    )
                    
                    migrated_count += 1
            
            logger.info(f"Diary migration completed. Migrated {migrated_count} entries.")
    except Exception as e:
        logger.error(f"Error migrating diary entries: {str(e)}", exc_info=True)
        raise

async def check_and_migrate_profile_data_column():
    """
    Check if the profile_data column exists in the users table and add it if not.
    """
    logger.info("Checking if profile_data column exists in users table...")
    
    try:
        # Create data directory if it doesn't exist
        os.makedirs(data_folder, exist_ok=True)
        
        # Check if database exists
        db_path = os.path.join(data_folder, 'timecapsule.db')
        if not os.path.exists(db_path):
            logger.info(f"Database does not exist at {db_path}. No migration needed.")
            return
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if profile_data column exists
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'profile_data' not in column_names:
            logger.info("Adding profile_data column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN profile_data TEXT DEFAULT '{}'")
            conn.commit()
            logger.info("profile_data column added successfully.")
        else:
            logger.info("profile_data column already exists. No migration needed.")
        
        # Close connection
        conn.close()
    except Exception as e:
        logger.error(f"Error during migration: {str(e)}", exc_info=True)
        raise

async def migrate_all():
    """Run all migrations."""
    try:
        # First check and migrate profile_data column
        # This needs to happen before any SQLAlchemy models are used
        await check_and_migrate_profile_data_column()
        
        # Initialize database
        await init_db()
        
        # Migrate users
        await migrate_users()
        
        # Migrate diary entries
        await migrate_diary_entries()
        
        logger.info("Migration completed successfully")
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(migrate_all()) 