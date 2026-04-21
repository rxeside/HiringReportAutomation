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
    "Королев Илья", "Миргаязов Руслан",
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
        self.events_df = pd.DataFrame()
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

            last_upd_row = state_df[state_df['key'] == 'last_updated']
            if not last_upd_row.empty: self.last_updated = last_upd_row.iloc[0]['value']

            order_row = state_df[state_df['key'] == 'statuses_order']
            if not order_row.empty: self.statuses_order = json.loads(order_row.iloc[0]['value'])

            if not raw_df.empty:
                self.df = raw_df.copy()
                date_cols = ['created_at', 'last_activity_at', 'offer_date', 'hired_date', 'vacancy_created_at']
                for col in date_cols:
                    if col in self.df.columns:
                        self.df[col] = (pd.to_datetime(self.df[col], errors='coerce') + pd.Timedelta(
                            hours=3)).dt.tz_localize(None)
                        if col == 'last_activity_at':
                            self.df['last_activity_at'] = self.df['last_activity_at'].fillna(self.df['created_at'])

                self.df['stage_index'] = self.df['current_status'].apply(
                    lambda x: FUNNEL_STAGES_ORDER.index(x) if x in FUNNEL_STAGES_ORDER else -1
                )

                events = []
                for _, row in self.df.iterrows():
                    try:
                        history = json.loads(row['stage_history']) if row['stage_history'] else []
                    except:
                        history = []
                    for ev in history:
                        events.append({
                            "applicant_id": row["applicant_id"],
                            "vacancy": row["vacancy"],
                            "vacancy_state": row["vacancy_state"],
                            "recruiter_id": ev.get("recruiter_id") or row["recruiter_id"],
                            "source": row["source"],
                            "hf_stage": ev.get("hf_stage"),
                            "custom_stage": ev.get("custom_stage"),
                            "date": ev.get("date")
                        })
                self.events_df = pd.DataFrame(events)
                if not self.events_df.empty:
                    self.events_df['date'] = (pd.to_datetime(self.events_df['date'], errors='coerce') + pd.Timedelta(
                        hours=3)).dt.tz_localize(None)

        except Exception as e:
            pass

    def get_filtered_stats(self, start_date: datetime, end_date: datetime,
                           vacancy_filter: List[str] = None, recruiter_filter: List[str] = None,
                           state_filter: List[str] = None):
        if self.events_df.empty: return self._empty_response()

        start = start_date.replace(tzinfo=None)
        end = end_date.replace(tzinfo=None)

        all_events = self.events_df.copy()
        all_events['date'] = all_events['date'].dt.tz_localize(None)

        all_events = all_events.sort_values(by=['applicant_id', 'date'])

        if vacancy_filter:
            all_events = all_events[all_events['vacancy'].isin(vacancy_filter)]

        all_events['rec_id_str'] = all_events['recruiter_id'].fillna(0).astype(int).astype(str)
        if recruiter_filter:
            target_ids = [str(x) for x in recruiter_filter]
        else:
            target_ids = [str(c_id) for c_id in self.coworkers.keys()]
        all_events = all_events[all_events['rec_id_str'].isin(target_ids)]

        if state_filter:
            all_events = all_events[all_events['vacancy_state'].isin(state_filter)]

        events_in_period = all_events[(all_events['date'] >= start) & (all_events['date'] <= end)].copy()

        if events_in_period.empty: return self._empty_response()

        unique_custom = events_in_period.dropna(subset=['custom_stage']).drop_duplicates(
            subset=['applicant_id', 'vacancy', 'custom_stage'], keep='first'
        )

        unique_hf = events_in_period.dropna(subset=['hf_stage']).drop_duplicates(
            subset=['applicant_id', 'vacancy', 'hf_stage'], keep='first'
        )

        first_stage_name = FUNNEL_STAGES_ORDER[0]
        total_candidates = len(unique_custom[unique_custom['custom_stage'] == first_stage_name])

        funnel_data = []
        prev_count = total_candidates
        for stage_name in FUNNEL_STAGES_ORDER:
            count = len(unique_custom[unique_custom['custom_stage'] == stage_name])
            c_step = round((count / prev_count) * 100, 1) if prev_count > 0 else 0
            c_total = round((count / total_candidates) * 100, 1) if total_candidates > 0 else 0
            funnel_data.append({
                "stage": stage_name, "count": count,
                "conversion_step": f"{c_step}%", "conversion_total": f"{c_total}%"
            })
            if count > 0: prev_count = count

        full_funnel_data = []
        hf_first_stage = self.statuses_order[0] if self.statuses_order else None
        hf_total = len(unique_hf[unique_hf['hf_stage'] == hf_first_stage]) if hf_first_stage else 0
        prev_hf = hf_total
        for stage_name in self.statuses_order:
            count = len(unique_hf[unique_hf['hf_stage'] == stage_name])
            c_step = round((count / prev_hf) * 100, 1) if prev_hf > 0 else 0
            c_total = round((count / hf_total) * 100, 1) if hf_total > 0 else 0
            full_funnel_data.append({
                "stage": stage_name, "count": count,
                "conversion_step": f"{c_step}%", "conversion_total": f"{c_total}%"
            })
            if count > 0: prev_hf = count

        unique_all_pairs = events_in_period[['applicant_id', 'vacancy']].drop_duplicates()
        filtered_df = self.df.merge(unique_all_pairs, on=['applicant_id', 'vacancy'])

        rejections_flat = []
        rejections_stacked = {}
        rej_df = filtered_df[filtered_df['rejection_reason'].notnull()]
        if not rej_df.empty:
            total_rej = len(rej_df)
            rej_counts = rej_df['rejection_reason'].value_counts().reset_index()
            rej_counts.columns = ['reason', 'count']
            for _, row in rej_counts.iterrows():
                rejections_flat.append({
                    "reason": row['reason'],
                    "count": row['count'],
                    "percent": f"{round((row['count'] / total_rej) * 100, 1)}%"
                })
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

        hired_df = filtered_df[filtered_df['hired_date'].notnull()].copy()
        avg_time = 0
        if not hired_df.empty and 'vacancy_created_at' in hired_df.columns:
            diff = (hired_df['hired_date'] - hired_df['vacancy_created_at']).dt.total_seconds() / 86400.0
            diff = diff[diff >= 0]
            if not diff.empty:
                avg_time = diff.mean()

        return {
            "total_candidates": total_candidates,
            "active_vacancies": int(events_in_period['vacancy'].nunique()),
            "funnel": funnel_data, "full_funnel": full_funnel_data,
            "rejections_flat": rejections_flat, "rejections_stacked": rejections_stacked,
            "sources": sources_data,
            "avg_time_to_close": round(avg_time, 1),
            "avg_time_to_offer": round(avg_time, 1),
            "coworkers": self.coworkers, "vacancies_list": sorted(self.df['vacancy'].unique().tolist())
        }

    def _empty_response(self):
        return {
            "total_candidates": 0, "active_vacancies": 0, "funnel": [], "full_funnel": [],
            "rejections_flat": [], "rejections_stacked": {}, "sources": [], "avg_time_to_offer": 0, "avg_time_to_close": 0,
            "coworkers": self.coworkers,
            "vacancies_list": sorted(self.df['vacancy'].unique().tolist()) if not self.df.empty else []
        }


engine = AnalyticsEngine("sqlite:///cache/huntflow.db")