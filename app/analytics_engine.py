import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import logging
from sqlalchemy import create_engine

FUNNEL_STAGES_ORDER = [
    "коннект", "интервью с HR", "интервью с заказчиком",
    "финальное интервью", "выставлен оффер",
    "вышел на работу", "испытательный срок пройден"
]


class AnalyticsEngine:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.db_engine = create_engine(self.db_url)
        self.df = pd.DataFrame()
        self.coworkers = {}
        self.last_updated = None

    def load_data(self):
        try:
            self.df = pd.read_sql_table("applicants", self.db_engine)

            coworkers_df = pd.read_sql_table("coworkers", self.db_engine)
            if not coworkers_df.empty:
                self.coworkers = dict(zip(coworkers_df['id'], coworkers_df['name']))

            state_df = pd.read_sql_table("system_state", self.db_engine)
            last_upd_row = state_df[state_df['key'] == 'last_updated']
            if not last_upd_row.empty:
                self.last_updated = last_upd_row.iloc[0]['value']

            if not self.df.empty:
                date_cols = ['created_at', 'offer_date', 'hired_date']
                for col in date_cols:
                    if col in self.df.columns:
                        self.df[col] = pd.to_datetime(self.df[col], errors='coerce').dt.tz_localize(None)

                self.df['stage_index'] = self.df['current_status'].apply(
                    lambda x: FUNNEL_STAGES_ORDER.index(x) if x in FUNNEL_STAGES_ORDER else -1
                )
            logging.info(f"Данные загружены из SQLite в Pandas. Всего строк: {len(self.df)}")
        except ValueError:
            logging.warning("Таблицы в БД пока не созданы или пусты. Нажмите 'Обновить'.")
        except Exception as e:
            logging.error(f"Ошибка при загрузке из БД: {e}")

    def get_filtered_stats(self,
                           start_date: datetime,
                           end_date: datetime,
                           vacancy_filter: List[str] = None,
                           recruiter_filter: List[str] = None,
                           state_filter: List[str] = None):

        if self.df.empty:
            return {}

        start = start_date.replace(tzinfo=None)
        end = end_date.replace(tzinfo=None)

        mask = (self.df['created_at'] >= start) & (self.df['created_at'] <= end)
        filtered_df = self.df[mask].copy()

        if vacancy_filter:
            filtered_df = filtered_df[filtered_df['vacancy'].isin(vacancy_filter)]

        if recruiter_filter:
            filtered_df['recruiter_id_str'] = filtered_df['recruiter_id'].astype(str)
            recruiter_filter_str = [str(x) for x in recruiter_filter]
            filtered_df = filtered_df[filtered_df['recruiter_id_str'].isin(recruiter_filter_str)]

        if state_filter:
            filtered_df = filtered_df[filtered_df['vacancy_state'].isin(state_filter)]

        if filtered_df.empty:
            return {"total_candidates": 0, "active_vacancies": 0, "funnel": [], "rejections_stacked": {},
                    "rejections_flat": [], "sources": []}

        funnel_data = []
        total_candidates = len(filtered_df)
        prev_count = total_candidates

        for i, stage_name in enumerate(FUNNEL_STAGES_ORDER):
            count = len(filtered_df[filtered_df['stage_index'] >= i])
            conversion_step = round((count / prev_count) * 100, 1) if prev_count > 0 else 0
            conversion_total = round((count / total_candidates) * 100, 1) if total_candidates > 0 else 0

            funnel_data.append({
                "stage": stage_name,
                "count": count,
                "conversion_step": f"{conversion_step}%",
                "conversion_total": f"{conversion_total}%"
            })
            prev_count = count

        rej_df = filtered_df[filtered_df['rejection_reason'].notnull()]

        rejections_stacked = {}
        if not rej_df.empty:
            rej_grouped = rej_df.groupby(['current_status', 'rejection_reason']).size().unstack(fill_value=0)
            rejections_stacked = rej_grouped.to_dict(orient='index')

        rejections_flat = []
        if not rej_df.empty:
            rejections_counts = rej_df['rejection_reason'].value_counts().reset_index()
            rejections_counts.columns = ['reason', 'count']
            rejections_flat = rejections_counts.to_dict('records')

        sources_data = []
        if not filtered_df.empty:
            for source, group in filtered_df.groupby('source'):
                total = len(group)
                hired = len(group[group['stage_index'] >= 5])
                probation = len(group[group['stage_index'] == 6])
                sources_data.append({
                    "source": str(source),
                    "total": total,
                    "hired": hired,
                    "probation": probation
                })

        hired_df = filtered_df[filtered_df['offer_date'].notnull()]
        avg_time_to_offer = 0
        if not hired_df.empty:
            avg_time_to_offer = (hired_df['offer_date'] - hired_df['created_at']).dt.days.mean()

        return {
            "total_candidates": total_candidates,
            "active_vacancies": int(filtered_df['vacancy'].nunique()),
            "funnel": funnel_data,
            "rejections_stacked": rejections_stacked,
            "rejections_flat": rejections_flat,
            "sources": sources_data,
            "avg_time_to_offer": round(avg_time_to_offer, 1),
            "coworkers": self.coworkers,
            "vacancies_list": sorted(self.df['vacancy'].unique().tolist())
        }


engine = AnalyticsEngine("sqlite:///cache/huntflow.db")