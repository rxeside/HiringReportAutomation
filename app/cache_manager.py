import asyncio
import json
import logging
import os
import traceback
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from . import report_generator
from .database import SessionLocal, Applicant, Coworker, SystemState
from .analytics_engine import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

_update_lock = asyncio.Lock()
_is_updating = False

async def load_cache() -> None:
    logging.info("Инициализация: Загрузка данных из SQLite в Pandas...")
    engine.load_data()

def _parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except Exception:
        return None

async def update_cached_data() -> None:
    global _is_updating
    if _update_lock.locked():
        logging.info("Обновление уже идет. Пропуск.")
        return

    async with _update_lock:
        _is_updating = True
        logging.info(">>> Начало загрузки данных в базу SQLite...")
        try:
            fetched_data = await report_generator.generate_raw_analytics_data()

            if fetched_data:
                try:
                    with open("cache/backup_raw_data.json", "w", encoding="utf-8") as f:
                        json.dump(fetched_data, f, ensure_ascii=False)
                    logging.info("Резервный бэкап данных сохранен.")
                except Exception as e:
                    logging.warning(f"Не удалось сохранить бэкап: {e}")

                db: Session = SessionLocal()
                try:
                    db.query(Coworker).delete()
                    for c_id, c_name in fetched_data['coworkers'].items():
                        db.add(Coworker(id=c_id, name=c_name))

                    db.query(Applicant).delete()
                    db_applicants = []
                    for a in fetched_data['applicants']:
                        first_log_date = a.get('created_at')
                        if a.get('logs'):
                            first_log_date = a['logs'][0].get('date', first_log_date)

                        db_applicants.append(Applicant(
                            applicant_id=a['id'],
                            vacancy=a['vacancy'],
                            vacancy_state=a['vacancy_state'],
                            recruiter_id=a['recruiter_id'],
                            source=a['source'],
                            created_at=_parse_date(first_log_date),
                            current_status=a.get('current_status'),
                            hf_status=a.get('hf_status'),
                            rejection_reason=a.get('rejection_reason'),
                            offer_date=_parse_date(a.get('offer_date')),
                            hired_date=_parse_date(a.get('hired_date')),
                            is_hired=a.get('is_hired', False)
                        ))
                    db.bulk_save_objects(db_applicants)

                    state_order = db.query(SystemState).filter_by(key="statuses_order").first()
                    order_json = json.dumps(fetched_data.get('statuses_order', []), ensure_ascii=False)
                    if not state_order:
                        db.add(SystemState(key="statuses_order", value=order_json))
                    else:
                        state_order.value = order_json

                    state = db.query(SystemState).filter_by(key="last_updated").first()
                    now_str = datetime.now(timezone.utc).isoformat()
                    if not state:
                        db.add(SystemState(key="last_updated", value=now_str))
                    else:
                        state.value = now_str

                    db.commit()
                    logging.info("База данных SQLite успешно обновлена.")
                except Exception as db_e:
                    db.rollback()
                    raise db_e
                finally:
                    db.close()

                engine.load_data()
            else:
                logging.warning("Сборщик вернул None, БД не обновлена.")
        except Exception as e:
            logging.error(f"Ошибка обновления: {e}\n{traceback.format_exc()}")
        finally:
            _is_updating = False
            logging.info("<<< Процесс обновления завершен.")

def get_update_status() -> bool:
    return _is_updating