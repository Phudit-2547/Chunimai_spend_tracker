import asyncpg
from datetime import date, datetime

from play_counter.config import DATABASE_URL


async def connect_db():
    return await asyncpg.connect(DATABASE_URL)


async def get_cumulative(game: str, date_str: str) -> int:
    conn = await connect_db()
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        col = f"{game}_cumulative"
        row = await conn.fetchrow(
            f"SELECT {col} FROM public.play_data WHERE play_date = $1", date_obj
        )
        return row[col] if row and row[col] is not None else 0
    finally:
        await conn.close()


async def upsert_play_data(
    date_str: str,
    maimai_new: int,
    chunithm_new: int,
    maimai_cumulative: int,
    chunithm_cumulative: int,
):
    conn = await connect_db()
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        await conn.execute(
            """
            INSERT INTO public.play_data
                (play_date, maimai_play_count, chunithm_play_count,
                 maimai_cumulative, chunithm_cumulative)
            VALUES ($1,$2,$3,$4,$5)
            ON CONFLICT (play_date) DO UPDATE
              SET maimai_play_count=EXCLUDED.maimai_play_count,
                  chunithm_play_count=EXCLUDED.chunithm_play_count,
                  maimai_cumulative=EXCLUDED.maimai_cumulative,
                  chunithm_cumulative=EXCLUDED.chunithm_cumulative
            """,
            date_obj,
            maimai_new,
            chunithm_new,
            maimai_cumulative,
            chunithm_cumulative,
        )
        print(
            f"✅ Data saved: {date} | Maimai new: {maimai_new}, Chunithm new: {chunithm_new} | "
            f"Maimai cumulative: {maimai_cumulative}, Chunithm cumulative: {chunithm_cumulative}"
        )
    finally:
        await conn.close()
