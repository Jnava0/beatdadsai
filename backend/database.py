@@ .. @@
 def init_db():
     """
-    Ensures the database schema is up-to-date.
-    Creates the 'agents' table and adds the 'allowed_tools' column if they don't exist.
+    Ensures the database schema is up-to-date with all required tables.
     """
     logger.info("Initializing the database schema...")
     db_manager = DatabaseManager()
     
-    # Define the table structure
+    # Agents table
     create_table_query = """
     CREATE TABLE IF NOT EXISTS agents (
         agent_id UUID PRIMARY KEY,
         name VARCHAR(255) NOT NULL,
         role TEXT NOT NULL,
         model_id VARCHAR(255) NOT NULL,
+        autonomy_level VARCHAR(50) DEFAULT 'medium',
+        communication_rights JSONB DEFAULT '[]'::jsonb,
+        memory_scope VARCHAR(50) DEFAULT 'task_limited',
         created_at TIMESTAMPTZ DEFAULT NOW()
     );
     """
     
-    # Define the column to add for tool permissions
-    # Using JSONB is highly flexible for storing lists of strings.
+    # Add allowed_tools column if it doesn't exist
     add_column_query = """
     ALTER TABLE agents
     ADD COLUMN IF NOT EXISTS allowed_tools JSONB DEFAULT '[]'::jsonb;
     """
     
+    # Tasks table for task scheduling
+    create_tasks_table = """
+    CREATE TABLE IF NOT EXISTS tasks (
+        task_id UUID PRIMARY KEY,
+        title VARCHAR(500) NOT NULL,
+        description TEXT,
+        assigned_agent UUID,
+        created_by VARCHAR(255) NOT NULL,
+        status VARCHAR(50) NOT NULL,
+        priority INTEGER DEFAULT 2,
+        created_at TIMESTAMPTZ DEFAULT NOW(),
+        updated_at TIMESTAMPTZ DEFAULT NOW(),
+        due_date TIMESTAMPTZ,
+        dependencies JSONB DEFAULT '[]'::jsonb,
+        subtasks JSONB DEFAULT '[]'::jsonb,
+        parent_task UUID,
+        metadata JSONB DEFAULT '{}'::jsonb,
+        progress FLOAT DEFAULT 0.0,
+        result TEXT,
+        error_message TEXT,
+        FOREIGN KEY (assigned_agent) REFERENCES agents(agent_id) ON DELETE SET NULL,
+        FOREIGN KEY (parent_task) REFERENCES tasks(task_id) ON DELETE CASCADE
+    );
+    """
+    
+    # Agent communications table for message logging
+    create_communications_table = """
+    CREATE TABLE IF NOT EXISTS agent_communications (
+        id SERIAL PRIMARY KEY,
+        message_id UUID NOT NULL,
+        sender_id VARCHAR(255) NOT NULL,
+        recipient_id VARCHAR(255) NOT NULL,
+        message_type VARCHAR(50) NOT NULL,
+        content TEXT,
+        metadata JSONB DEFAULT '{}'::jsonb,
+        timestamp TIMESTAMPTZ DEFAULT NOW(),
+        conversation_id UUID
+    );
+    """
+    
+    # Knowledge base table for autonomous learning
+    create_knowledge_table = """
+    CREATE TABLE IF NOT EXISTS knowledge_base (
+        id SERIAL PRIMARY KEY,
+        title VARCHAR(500),
+        content TEXT NOT NULL,
+        source_url VARCHAR(1000),
+        source_type VARCHAR(100),
+        scraped_at TIMESTAMPTZ DEFAULT NOW(),
+        embedding_vector VECTOR(1536),  -- Assuming OpenAI-style embeddings
+        metadata JSONB DEFAULT '{}'::jsonb,
+        tags TEXT[],
+        created_by VARCHAR(255)
+    );
+    """
+    
+    # Agent memory table for persistent agent memory
+    create_memory_table = """
+    CREATE TABLE IF NOT EXISTS agent_memory (
+        id SERIAL PRIMARY KEY,
+        agent_id UUID NOT NULL,
+        memory_type VARCHAR(100) NOT NULL,
+        content TEXT NOT NULL,
+        importance_score FLOAT DEFAULT 0.5,
+        created_at TIMESTAMPTZ DEFAULT NOW(),
+        last_accessed TIMESTAMPTZ DEFAULT NOW(),
+        metadata JSONB DEFAULT '{}'::jsonb,
+        embedding_vector VECTOR(1536),
+        FOREIGN KEY (agent_id) REFERENCES agents(agent_id) ON DELETE CASCADE
+    );
+    """
+    
+    # System logs table
+    create_logs_table = """
+    CREATE TABLE IF NOT EXISTS system_logs (
+        id SERIAL PRIMARY KEY,
+        level VARCHAR(20) NOT NULL,
+        message TEXT NOT NULL,
+        module VARCHAR(100),
+        agent_id UUID,
+        timestamp TIMESTAMPTZ DEFAULT NOW(),
+        metadata JSONB DEFAULT '{}'::jsonb,
+        FOREIGN KEY (agent_id) REFERENCES agents(agent_id) ON DELETE SET NULL
+    );
+    """
+    
+    # Create indexes for better performance
+    create_indexes = [
+        "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);",
+        "CREATE INDEX IF NOT EXISTS idx_tasks_assigned_agent ON tasks(assigned_agent);",
+        "CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);",
+        "CREATE INDEX IF NOT EXISTS idx_communications_timestamp ON agent_communications(timestamp);",
+        "CREATE INDEX IF NOT EXISTS idx_communications_conversation ON agent_communications(conversation_id);",
+        "CREATE INDEX IF NOT EXISTS idx_memory_agent_id ON agent_memory(agent_id);",
+        "CREATE INDEX IF NOT EXISTS idx_memory_type ON agent_memory(memory_type);",
+        "CREATE INDEX IF NOT EXISTS idx_knowledge_source_type ON knowledge_base(source_type);",
+        "CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON system_logs(timestamp);",
+        "CREATE INDEX IF NOT EXISTS idx_logs_agent_id ON system_logs(agent_id);"
+    ]
+    
     try:
         db_manager.execute_query(create_table_query)
         db_manager.execute_query(add_column_query)
-        logger.info("'agents' table is up-to-date.")
+        db_manager.execute_query(create_tasks_table)
+        db_manager.execute_query(create_communications_table)
+        db_manager.execute_query(create_knowledge_table)
+        db_manager.execute_query(create_memory_table)
+        db_manager.execute_query(create_logs_table)
+        
+        # Create indexes
+        for index_query in create_indexes:
+            db_manager.execute_query(index_query)
+        
+        logger.info("Database schema is up-to-date with all required tables.")
     except Exception as e:
         logger.critical(f"Could not initialize the database schema: {e}")
         exit(1)