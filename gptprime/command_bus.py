import sqlite3
import json
import uuid
import datetime
import threading
import os

class CommandBus:
    ROUTING = {
        "research":    ["gpt_researcher", "open_agents"],
        "code":        ["gpt_engineer", "meta_gpt"],
        "swarm":       ["gpt_swarm", "swarms_agent"],
        "execute":     ["auto_gpt", "agent_gpt"],
        "monitor":     ["magicrew"],
        "orchestrate": ["meta_gpt", "crew_ai"],
        "analyze":     ["open_agents", "gpt_researcher"],
        "stealth":     ["web_gpt"],
        "memory":      [],  # handled internally
        "broadcast":   []   # all agents
    }

    def __init__(self, db_path="gptprime/command_bus.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    topic TEXT,
                    payload TEXT,
                    sender TEXT,
                    priority INTEGER,
                    status TEXT,
                    created_at TIMESTAMP,
                    processed_at TIMESTAMP,
                    result TEXT,
                    error TEXT,
                    retry_count INTEGER DEFAULT 0,
                    pipeline_id TEXT,
                    step_index INTEGER
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    agent_name TEXT,
                    topic TEXT,
                    PRIMARY KEY (agent_name, topic)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pipelines (
                    id TEXT PRIMARY KEY,
                    steps TEXT,
                    current_step INTEGER,
                    status TEXT
                )
            """)
            conn.commit()
            conn.close()

    def publish(self, topic, payload, sender, priority=1, pipeline_id=None, step_index=None):
        msg_id = str(uuid.uuid4())
        created_at = datetime.datetime.now().isoformat()
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (id, topic, payload, sender, priority, status, created_at, retry_count, pipeline_id, step_index)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (msg_id, topic, json.dumps(payload), sender, priority, 'queued', created_at, 0, pipeline_id, step_index))
            conn.commit()
            conn.close()
        return msg_id

    def subscribe(self, agent_name, topics):
        if isinstance(topics, str):
            topics = [topics]
        # Always subscribe agent to their own name for direct routing
        all_topics = set(topics) | {agent_name}
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            for topic in all_topics:
                cursor.execute("INSERT OR IGNORE INTO subscriptions (agent_name, topic) VALUES (?, ?)", (agent_name, topic))
            conn.commit()
            conn.close()

    def consume(self, agent_name):
        """
        Returns highest-priority queued message for any of the agent's subscribed topics.
        Marks message as 'processing' atomically.
        """
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            # Find topics agent is subscribed to
            cursor.execute("SELECT topic FROM subscriptions WHERE agent_name = ?", (agent_name,))
            topics = [row[0] for row in cursor.fetchall()]
            
            if not topics:
                conn.close()
                return None

            # Get the highest priority queued message for these topics
            placeholders = ','.join(['?'] * len(topics))
            query = f"""
                SELECT id, topic, payload, sender, priority, pipeline_id, step_index 
                FROM messages 
                WHERE status = 'queued' AND topic IN ({placeholders})
                ORDER BY priority DESC, created_at ASC 
                LIMIT 1
            """
            cursor.execute(query, topics)
            row = cursor.fetchone()
            
            if row:
                msg_id = row[0]
                # Atomic update to 'processing'
                cursor.execute("UPDATE messages SET status = 'processing' WHERE id = ?", (msg_id,))
                conn.commit()
                
                message = {
                    "id": row[0],
                    "topic": row[1],
                    "payload": json.loads(row[2]),
                    "sender": row[3],
                    "priority": row[4],
                    "pipeline_id": row[5],
                    "step_index": row[6]
                }
                conn.close()
                return message
            
            conn.close()
            return None

    def ack(self, msg_id, result=None):
        processed_at = datetime.datetime.now().isoformat()
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE messages 
                SET status = 'done', result = ?, processed_at = ? 
                WHERE id = ?
            """, (json.dumps(result) if result else None, processed_at, msg_id))
            conn.commit()
            conn.close()

    def nack(self, msg_id, error=None, retry=True):
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            if retry:
                # Requeue with priority - 1
                cursor.execute("""
                    UPDATE messages 
                    SET status = 'queued', error = ?, priority = priority - 1
                    WHERE id = ?
                """, (str(error), msg_id))
            else:
                cursor.execute("""
                    UPDATE messages 
                    SET status = 'failed', error = ? 
                    WHERE id = ?
                """, (str(error), msg_id))
            conn.commit()
            conn.close()

    def pipeline(self, steps, sender):
        pipeline_id = str(uuid.uuid4())
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO pipelines (id, steps, current_step, status)
                VALUES (?, ?, ?, ?)
            """, (pipeline_id, json.dumps(steps), 0, 'active'))
            conn.commit()
            conn.close()
        
        # Publish first step
        if steps:
            first_step = steps[0]
            self.publish(
                topic=first_step["topic"],
                payload=first_step["payload"],
                sender=sender,
                pipeline_id=pipeline_id,
                step_index=0
            )
        return pipeline_id

    def broadcast(self, payload, sender):
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT agent_name FROM subscriptions")
            agents = [row[0] for row in cursor.fetchall()]
            conn.close()
        
        msg_ids = []
        for agent in agents:
            # Direct route to each agent
            msg_ids.append(self.publish(agent, payload, sender))
        return msg_ids

    def stats(self):
        with self.lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            stats = {}
            
            cursor.execute("SELECT status, COUNT(*) FROM messages GROUP BY status")
            for status, count in cursor.fetchall():
                stats[f"{status}_count"] = count
            
            cursor.execute("SELECT topic, COUNT(*) FROM messages GROUP BY topic")
            stats["topic_counts"] = {topic: count for topic, count in cursor.fetchall()}
            
            cursor.execute("""
                SELECT s.agent_name, COUNT(m.id) 
                FROM subscriptions s 
                LEFT JOIN messages m ON s.topic = m.topic 
                GROUP BY s.agent_name
            """)
            stats["agent_counts"] = {agent: count for agent, count in cursor.fetchall()}
            
            conn.close()
            return stats

    def auto_route(self, topic, payload, sender):
        agents = self.ROUTING.get(topic, [])
        if not agents:
            # Fallback to normal pub/sub if topic not in routing table
            return [self.publish(topic, payload, sender)]
        
        msg_ids = []
        for agent in agents:
            # Direct route to all agents mapped to this topic
            msg_ids.append(self.publish(agent, payload, sender))
        return msg_ids

if __name__ == "__main__":
    bus = CommandBus("gptprime/test_bus.db")
    
    # 1. Subscribe agents
    bus.subscribe("gpt_researcher", ["research"])
    bus.subscribe("gpt_engineer", ["code"])
    bus.subscribe("magicrew", ["monitor"])
    
    # 2. Publish messages
    bus.publish("research", {"query": "Pantheon architecture"}, "meta_gpt", priority=5)
    bus.publish("code", {"task": "implement bus"}, "meta_gpt")
    bus.publish("monitor", {"alert": "system low memory"}, "system")
    
    # Broadcast test
    bus.broadcast({"msg": "Hello all"}, "meta_gpt")
    
    # Auto-route test
    bus.auto_route("research", {"query": "Auto-routed research"}, "meta_gpt")
    
    # 3. Consume and ACK
    print("Consuming for gpt_researcher...")
    while True:
        msg = bus.consume("gpt_researcher")
        if not msg: break
        print(f"Researcher got: {msg['topic']} -> {msg['payload']}")
        bus.ack(msg['id'], result={"data": "DONE"})
        
    print("\nConsuming for gpt_engineer...")
    while True:
        msg = bus.consume("gpt_engineer")
        if not msg: break
        print(f"Engineer got: {msg['topic']} -> {msg['payload']}")
        bus.ack(msg['id'], result={"code": "DONE"})

    # 4. Pipeline demo
    print("\nStarting pipeline...")
    pipeline_steps = [
        {"topic": "research", "payload": {"q": "step 1"}},
        {"topic": "code", "payload": {"q": "step 2"}}
    ]
    pipe_id = bus.pipeline(pipeline_steps, "meta_gpt")
    print(f"Pipeline created: {pipe_id}")
    
    # 5. Stats
    print(f"\nStats: {bus.stats()}")
    
    # Cleanup test DB
    if os.path.exists("gptprime/test_bus.db"):
        os.remove("gptprime/test_bus.db")
    print("\nDemo complete.")
