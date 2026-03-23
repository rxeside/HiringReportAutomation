import json
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

ALLOWED_RECRUITERS = [
    "Бреднева Софья", "Королев Илья", "Миргаязов Руслан",
    "Прокопьева Анастасия", "Таныгина Кристина", "Чихалова Татьяна",
    "Щербик Софья", "Игнатенко Валерия", "Бреднева Светлана"
]


def _is_allowed_recruiter(hf_name: str) -> bool:
    hf_lower = hf_name.lower()
    for allowed_name in ALLOWED_RECRUITERS:
        parts = allowed_name.lower().split()
        if all(part in hf_lower for part in parts): return True
    return False


class AnalyticsEngine:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.db_engine = create_engine(self.db_url)
        self.df = pd.DataFrame()
        self.coworkers = {}
        self.last_updated = None
        self.statuses_order = []

    def load_data(self):
        try:
            raw_df = pd.read_sql_table("applicants", self.db_engine)
            coworkers_df = pd.read_sql_table("coworkers", self.db_engine)
            state_df = pd.read_sql_table("system_state", self.db_engine)

            full_coworkers = {}
            if not coworkers_df.empty:
                full_coworkers = dict(zip(coworkers_df['id'], coworkers_df['name']))

            self.coworkers = {c_id: name for c_id, name in full_coworkers.items() if _is_allowed_recruiter(name)}
            allowed_ids = list(self.coworkers.keys())

            last_upd_row = state_df[state_df['key'] == 'last_updated']
            if not last_upd_row.empty: self.last_updated = last_upd_row.iloc[0]['value']

            order_row = state_df[state_df['key'] == 'statuses_order']
            if not order_row.empty: self.statuses_order = json.loads(order_row.iloc[0]['value'])

            if not raw_df.empty:
                # self.df = raw_df[raw_df['recruiter_id'].isin(allowed_ids)].copy()
                self.df = raw_df.copy()

                date_cols = ['created_at', 'offer_date', 'hired_date']
                for col in date_cols:
                    if col in self.df.columns:
                        self.df[col] = pd.to_datetime(self.df[col], errors='coerce').dt.tz_localize(None)

                self.df['stage_index'] = self.df['current_status'].apply(
                    lambda x: FUNNEL_STAGES_ORDER.index(x) if x in FUNNEL_STAGES_ORDER else -1
                )
                status_to_order = {name: i for i, name in enumerate(self.statuses_order)}
                self.df['full_stage_index'] = self.df['hf_status'].map(status_to_order).fillna(-1)

        except Exception as e:
            pass

    def get_filtered_stats(self, start_date: datetime, end_date: datetime,
                           vacancy_filter: List[str] = None, recruiter_filter: List[str] = None,
                           state_filter: List[str] = None):

        if self.df.empty: return self._empty_response()

        start = start_date.replace(tzinfo=None)
        end = end_date.replace(tzinfo=None)

        def is_active_in_period(row):
            if pd.notnull(row['created_at']) and start <= row['created_at'] <= end:
                return True

            log_dates_str = row.get('log_dates')
            if pd.notnull(log_dates_str) and log_dates_str:
                try:
                    dates = json.loads(log_dates_str)
                    for d_str in dates:
                        d = datetime.fromisoformat(d_str[:19])
                        if start <= d <= end:
                            return True
                except Exception:
                    pass
            return False

        mask = self.df.apply(is_active_in_period, axis=1)
        filtered_df = self.df[mask].copy()

        if vacancy_filter: filtered_df = filtered_df[filtered_df['vacancy'].isin(vacancy_filter)]
        if recruiter_filter:
            filtered_df['recruiter_id_str'] = filtered_df['recruiter_id'].fillna(0).astype(int).astype(str)
            recruiter_filter_str = [str(x) for x in recruiter_filter]
            filtered_df = filtered_df[filtered_df['recruiter_id_str'].isin(recruiter_filter_str)]
        if state_filter: filtered_df = filtered_df[filtered_df['vacancy_state'].isin(state_filter)]

        if filtered_df.empty: return self._empty_response()

        total_candidates = len(filtered_df)

        funnel_data = []
        prev_count = total_candidates

        for i, stage_name in enumerate(FUNNEL_STAGES_ORDER):
            count = len(filtered_df[filtered_df['stage_index'] >= i])
            conversion_step = round((count / prev_count) * 100, 1) if prev_count > 0 else 0
            conversion_total = round((count / total_candidates) * 100, 1) if total_candidates > 0 else 0

            funnel_data.append({
                "stage": stage_name, "count": count,
                "conversion_step": f"{conversion_step}%", "conversion_total": f"{conversion_total}%"
            })
            prev_count = count

        full_funnel_data = []
        prev_count_full = total_candidates
        for i, stage_name in enumerate(self.statuses_order):
            count = len(filtered_df[filtered_df['full_stage_index'] >= i])
            if count == 0 and prev_count_full == 0: continue

            conversion_step = round((count / prev_count_full) * 100, 1) if prev_count_full > 0 else 0
            conversion_total = round((count / total_candidates) * 100, 1) if total_candidates > 0 else 0
            full_funnel_data.append({
                "stage": stage_name, "count": count,
                "conversion_step": f"{conversion_step}%", "conversion_total": f"{conversion_total}%"
            })
            prev_count_full = count

        rejections_flat = []
        rejections_stacked = {}
        rej_df = filtered_df[filtered_df['rejection_reason'].notnull()]

        if not rej_df.empty:
            total_rejections = len(rej_df)
            rejections_counts = rej_df['rejection_reason'].value_counts().reset_index()
            rejections_counts.columns = ['reason', 'count']

            for _, row in rejections_counts.iterrows():
                percent = round((row['count'] / total_rejections) * 100, 1)
                rejections_flat.append({"reason": row['reason'], "count": row['count'], "percent": f"{percent}%"})

            rej_grouped = rej_df.groupby(['current_status', 'rejection_reason']).size().unstack(fill_value=0)
            available_stages = [s for s in FUNNEL_STAGES_ORDER if s in rej_grouped.index]
            rejections_stacked = rej_grouped.reindex(available_stages).to_dict(orient='index')

        sources_data = []
        if not filtered_df.empty:
            for source, group in filtered_df.groupby('source'):
                sources_data.append({
                    "source": str(source), "total": len(group),
                    "hired": len(group[group['stage_index'] >= 5]),
                    "probation": len(group[group['stage_index'] == 6])
                })

        hired_df = filtered_df[filtered_df['offer_date'].notnull()]
        avg_time_to_offer = 0
        if not hired_df.empty:
            avg_time_to_offer = (hired_df['offer_date'] - hired_df['created_at']).dt.days.mean()

        return {
            "total_candidates": total_candidates,
            "active_vacancies": int(filtered_df['vacancy'].nunique()),
            "funnel": funnel_data,
            "full_funnel": full_funnel_data,
            "rejections_flat": rejections_flat,
            "rejections_stacked": rejections_stacked,
            "sources": sources_data,
            "avg_time_to_offer": round(avg_time_to_offer, 1),
            "coworkers": self.coworkers,
            "vacancies_list": sorted(self.df['vacancy'].unique().tolist())
        }

    def _empty_response(self):
        """Возвращает безопасный пустой ответ, чтобы фронт не падал в undefined"""
        return {
            "total_candidates": 0, "active_vacancies": 0,
            "funnel": [], "full_funnel": [], "rejections_flat": [], "rejections_stacked": {},
            "sources": [], "avg_time_to_offer": 0, "coworkers": self.coworkers,
            "vacancies_list": sorted(self.df['vacancy'].unique().tolist()) if not self.df.empty else []
        }


engine = AnalyticsEngine("sqlite:///cache/huntflow.db")