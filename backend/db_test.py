import asyncio
from datetime import datetime
from database.connection import connect, disconnect, get_db, get_session_id

async def run_test():
    print("1. DB 연결 및 스키마 초기화")
    await connect()
    
    current_session = get_session_id()
    print(f"세션 ID: {current_session}")
    
    db = await get_db()

    print("\n각 Tier별 더미 데이터 삽입")
    try:
        # Tier 1: Turns 
        await db.execute(
            "INSERT INTO turns (session_id, turn_num, role, content, token_count) VALUES (?, ?, ?, ?, ?)",
            (current_session, 1, "user", "안녕! 나는 티라노사우루스가 좋아.", 15)
        )
        await db.execute(
            "INSERT INTO turns (session_id, turn_num, role, content, token_count) VALUES (?, ?, ?, ?, ?)",
            (current_session, 2, "assistant", "안녕! 티라노사우루스를 좋아하는구나. 고기가 먹고 싶니?", 20)
        )
        
        # Tier 2: Facts 
        await db.execute(
            "INSERT INTO facts (category, content, importance, source_session) VALUES (?, ?, ?, ?)",
            ("preference", "공룡 중 티라노사우루스를 가장 좋아함", 3, current_session)
        )
        
        # Tier 3: Session Summaries 
        now_str = datetime.now().isoformat()
        await db.execute(
            "INSERT INTO session_summaries (session_id, summary, token_count, started_at, ended_at) VALUES (?, ?, ?, ?, ?)",
            (current_session, "아이가 공룡(티라노사우루스)을 좋아한다고 말하며 첫인사를 나눔.", 35, now_str, now_str)
        )
        
        await db.commit()
        print("데이터 삽입 완료!")

    except Exception as e:
        print(f"데이터 삽입 중 에러 발생: {e}")

    print("\n삽입된 데이터 조회 테스트")
    
    print("--- [Tier 1] Turns ---")
    async with db.execute("SELECT * FROM turns ORDER BY turn_num ASC") as cursor:
        async for row in cursor:
            print(dict(row))

    print("\n--- [Tier 2] Facts ---")
    async with db.execute("SELECT * FROM facts") as cursor:
        async for row in cursor:
            print(dict(row))

    print("\n--- [Tier 3] Session Summaries ---")
    async with db.execute("SELECT * FROM session_summaries") as cursor:
        async for row in cursor:
            print(dict(row))

    print("\nDB 연결 정상 종료...")
    await disconnect()

if __name__ == "__main__":
    asyncio.run(run_test())