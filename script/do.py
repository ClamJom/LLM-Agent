import sqlite3
from setting import settings

# 使用SQLITE作为数据库，当然也可以用其它的数据库，实现就好......


def create_conversation_database():
    conn = sqlite3.connect(settings.SQLITE_DATABASE_PATH, check_same_thread=False)
    cursor = conn.cursor()

    # Create a table to store conversations
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    timestamp TEXT
                )"""
    )

    conn.commit()
    conn.close()


def create_message_database():
    conn = sqlite3.connect(settings.SQLITE_DATABASE_PATH, check_same_thread=False)
    cursor = conn.cursor()

    # Create a table to store messages
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER,
                    role TEXT,
                    content TEXT,
                    timestamp TEXT,
                    attachments TEXT
                )"""
    )

    conn.commit()
    conn.close()


def init_database():
    create_conversation_database()
    create_message_database()


def get_conversations():
    conn = sqlite3.connect(settings.SQLITE_DATABASE_PATH, check_same_thread=False)
    cursor = conn.cursor()
    conversations = cursor.execute("SELECT * FROM conversations").fetchall()
    conn.close()
    return conversations


def insert_conversation(title, timestamp):
    conn = sqlite3.connect(settings.SQLITE_DATABASE_PATH, check_same_thread=False)
    cursor = conn.cursor()

    # Insert a new conversation into the table
    cursor.execute(
        """INSERT INTO conversations (title, timestamp)
                    VALUES (?, ?)""",
        (title, timestamp),
    )

    conn.commit()
    conversation_id = cursor.lastrowid
    conn.close()
    return conversation_id


def insert_message(conversation, role, content, timestamp, attachments):
    conn = sqlite3.connect(settings.SQLITE_DATABASE_PATH, check_same_thread=False)
    cursor = conn.cursor()

    # Insert a new message into the table
    cursor.execute(
        """INSERT INTO messages (role, content, timestamp)
                    VALUES (?, ?, ?, ?, attachments)""",
        (conversation, role, content, timestamp, attachments),
    )

    conn.commit()
    conn.close()


def get_messages(conversation_id):
    conn = sqlite3.connect(settings.SQLITE_DATABASE_PATH, check_same_thread=False)
    cursor = conn.cursor()
    messages = cursor.execute(
        "SELECT * FROM messages WHERE conversation_id = ?", (conversation_id,)
    )
    result = []
    for message in messages:
        result.append(
            {
                "role": message[2],
                "content": message[3],
                "timestamp": message[4],
                "attachments": message[5],
            }
        )
    conn.close()
    return result


def update_messages(conversation_id, messages: list[dict]):
    conn = sqlite3.connect(settings.SQLITE_DATABASE_PATH, check_same_thread=False)
    cursor = conn.cursor()
    for message in messages:
        if "attachments" not in message:
            message["attachments"] = "[]"
        else:
            message["attachments"] = str(message["attachments"])
        exist_msg = cursor.execute(
            "SELECT * FROM messages WHERE conversation_id = ? AND role = ? AND content = ? AND timestamp = ?",
            (
                conversation_id,
                message["role"],
                message["content"],
                message["timestamp"],
            ),
        ).fetchone()
        if not exist_msg:
            cursor.execute(
                "INSERT INTO messages (conversation_id, role, content, timestamp, attachments) VALUES (?, ?, ?, ?, ?)",
                (
                    conversation_id,
                    message["role"],
                    message["content"],
                    message["timestamp"],
                    message["attachments"],
                ),
            )
            conn.commit()
    conn.close()


def delete_conversation(conversation_id):
    conn = sqlite3.connect(settings.SQLITE_DATABASE_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    conn.close()
