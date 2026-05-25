import time
import threading
import json
import sqlite3
import datetime
import math
import uuid
from gptprime.tool_forge import get_forge

class BusWorker:
    """
    Background worker for the CommandBus.
    Handles retries, pipeline advancement, and monitoring.
    """
    def __init__(self, bus):
        self.bus = bus
        self.running = False
        self.thread = None
        self.forge = get_forge()

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, name="BusWorker", daemon=True)
        self.thread.start()
        print("BusWorker started.")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
            print("BusWorker stopped.")

    def _loop(self):
        while self.running:
            try:
                self._handle_retries()
                self._handle_pipelines()
            except Exception as e:
                # Log error but don't stop the worker
                print(f"BusWorker Loop Error: {e}")
            time.sleep(2)

    def _handle_retries(self):
        """
        Retries failed messages up to 3 times with exponential backoff.
        Sends a Telegram alert if any message fails all 3 retries.
        """
        with self.bus.lock:
            conn = sqlite3.connect(self.bus.db_path)
            cursor = conn.cursor()
            
            # Find messages that failed and haven't exhausted retries
            cursor.execute("""
                SELECT id, topic, sender, retry_count, error, created_at 
                FROM messages 
                WHERE status = 'failed' AND retry_count < 3
            """)
            failed_msgs = cursor.fetchall()
            
            now = datetime.datetime.now()
            for msg_id, topic, sender, retry_count, error, created_at in failed_msgs:
                # Exponential backoff: 2^retry_count * 10 seconds
                wait_time = math.pow(2, retry_count) * 10
                created_dt = datetime.datetime.fromisoformat(created_at)
                
                if (now - created_dt).total_seconds() >= wait_time:
                    # Requeue
                    cursor.execute("""
                        UPDATE messages 
                        SET status = 'queued', retry_count = retry_count + 1 
                        WHERE id = ?
                    """, (msg_id,))
                    print(f"Retrying message {msg_id} (topic: {topic}, attempt {retry_count + 1})")
            
            # Find messages that exhausted retries and haven't been alerted yet
            # We can use a special status or a column, but let's just use status='failed' and retry_count=3
            cursor.execute("""
                SELECT id, topic, sender, error 
                FROM messages 
                WHERE status = 'failed' AND retry_count >= 3
            """)
            exhausted = cursor.fetchall()
            for msg_id, topic, sender, error in exhausted:
                # Mark as 'alerted' (reusing error column or just alert once?)
                # To avoid spamming, we could add a column or a table for alerts.
                # For now, let's just mark status as 'permanently_failed'
                cursor.execute("UPDATE messages SET status = 'permanently_failed' WHERE id = ?", (msg_id,))
                
                alert_msg = f"⚠️ *CommandBus Alert*\nTask failed after 3 retries.\nID: `{msg_id}`\nTopic: `{topic}`\nSender: `{sender}`\nError: `{error}`"
                self.forge.run("telegram_send", message=alert_msg)
                print(f"Alerted Forgemaster about exhausted retries for {msg_id}")

            conn.commit()
            conn.close()

    def _handle_pipelines(self):
        """
        Advance pipelines: Each step is published only after the previous ACKs.
        """
        with self.bus.lock:
            conn = sqlite3.connect(self.bus.db_path)
            cursor = conn.cursor()
            
            # Find messages that are 'done' and part of an active pipeline
            # and whose step matches the current_step of the pipeline.
            cursor.execute("""
                SELECT m.id, m.pipeline_id, m.step_index, p.steps, p.current_step, m.sender
                FROM messages m
                JOIN pipelines p ON m.pipeline_id = p.id
                WHERE m.status = 'done' AND p.status = 'active' AND m.step_index = p.current_step
            """)
            active_steps = cursor.fetchall()
            
            for msg_id, pipe_id, step_index, steps_json, current_step, sender in active_steps:
                steps = json.loads(steps_json)
                next_step_idx = current_step + 1
                
                if next_step_idx < len(steps):
                    # Trigger next step
                    next_step = steps[next_step_idx]
                    
                    # We must release the lock or use a different connection if we call publish
                    # But we are inside a with self.bus.lock block. 
                    # Better to update the DB directly here or collect and publish outside.
                    
                    # Update pipeline current_step
                    cursor.execute("UPDATE pipelines SET current_step = ? WHERE id = ?", (next_step_idx, pipe_id))
                    
                    # Create the next message
                    new_msg_id = str(uuid.uuid4())
                    created_at = datetime.datetime.now().isoformat()
                    
                    cursor.execute("""
                        INSERT INTO messages (id, topic, payload, sender, priority, status, created_at, retry_count, pipeline_id, step_index)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (new_msg_id, next_step["topic"], json.dumps(next_step["payload"]), sender, 1, 'queued', created_at, 0, pipe_id, next_step_idx))
                    
                    print(f"Pipeline {pipe_id}: Advancing to step {next_step_idx} ({next_step['topic']})")
                else:
                    # Pipeline completed
                    cursor.execute("UPDATE pipelines SET status = 'completed' WHERE id = ?", (pipe_id,))
                    print(f"Pipeline {pipe_id}: Completed.")
            
            conn.commit()
            conn.close()
