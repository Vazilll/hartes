import os
import sys
import time
import json
import sqlite3
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

# Ensure UTF-8 output on Windows
sys.stdout.reconfigure(encoding='utf-8')
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

DB_PATH = r"C:\vazus\services\memory\vazus.db"
CREDENTIALS_FILE = r"C:\vazus\credentials.json"
TOKEN_FILE = r"C:\vazus\token.json"

SCOPES = [
    'https://www.googleapis.com/auth/fitness.activity.read',
    'https://www.googleapis.com/auth/fitness.body.read',
    'https://www.googleapis.com/auth/fitness.heart_rate.read',
    'https://www.googleapis.com/auth/fitness.sleep.read',
    'https://www.googleapis.com/auth/fitness.oxygen_saturation.read'
]

def get_google_fit_service():
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as e:
            print(f"Error loading token: {e}")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            try:
                creds.refresh(Request())
            except Exception as re:
                print(f"Token refresh failed: {re}")
                creds = None
        
        if not creds:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"ERROR: {CREDENTIALS_FILE} not found!")
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES, autogenerate_code_verifier=False)
            flow.redirect_uri = 'http://localhost:8090/'
            auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
            
            try:
                webbrowser.open(auth_url)
            except Exception as e:
                print(f"Warning: Could not open browser automatically ({e}). Please open this URL: {auth_url}")

            server_address = ('', 8090)
            httpd = HTTPServer(server_address, BaseHTTPRequestHandler)
            httpd.handle_request()
            creds = flow.credentials
        
        with open(TOKEN_FILE, 'w', encoding='utf-8') as token_out:
            token_out.write(creds.to_json())

    return build('fitness', 'v1', credentials=creds)

def fetch_and_save_fitness_data():
    service = get_google_fit_service()
    if not service:
        return False

    now = datetime.now()
    start_time = now - timedelta(days=4)
    
    start_ns = int(start_time.timestamp() * 1e9)
    end_ns = int(now.timestamp() * 1e9)
    start_iso = start_time.strftime('%Y-%m-%dT00:00:00Z')
    end_iso = now.strftime('%Y-%m-%dT23:59:59Z')

    metrics_summary = {}

    # 1. Fetch Sessions API (Sleep & Workouts)
    try:
        sessions_res = service.users().sessions().list(userId='me', startTime=start_iso, endTime=end_iso).execute()
        sessions = sessions_res.get('session', [])
        
        sleep_sessions = []
        workouts = []
        activity_names = {
            1: 'Ходьба/Активность',
            7: 'Ходьба',
            8: 'Бег',
            15: 'Велосипед (Cycling)',
            17: 'Шоссейный велосипед',
            59: 'Велосипед / Футбол',
            72: 'Сон'
        }
        
        for s in sessions:
            st = datetime.fromtimestamp(int(s['startTimeMillis'])/1000)
            et = datetime.fromtimestamp(int(s['endTimeMillis'])/1000)
            dur_m = round((et - st).total_seconds() / 60.0, 1)
            act_code = s.get('activityType')
            name = s.get('name') or activity_names.get(act_code, f"Activity {act_code}")
            
            if act_code == 72:
                sleep_sessions.append({
                    "date": st.strftime('%Y-%m-%d'),
                    "start": st.strftime('%H:%M'),
                    "end": et.strftime('%H:%M'),
                    "duration_hours": round(dur_m / 60.0, 2)
                })
            else:
                workouts.append({
                    "date": st.strftime('%Y-%m-%d'),
                    "name": name,
                    "start": st.strftime('%H:%M'),
                    "end": et.strftime('%H:%M'),
                    "duration_min": dur_m
                })

        metrics_summary['sleep_sessions'] = sleep_sessions
        metrics_summary['workouts'] = workouts
    except Exception as e:
        print(f"Error fetching Sessions: {e}")

    # 2. Fetch Sleep Stage Breakdown (raw/derived datasets)
    try:
        dataset_id = f"{start_ns}-{end_ns}"
        ds_id = "raw:com.google.sleep.segment:com.xiaomi.wearable:health_platform"
        try:
            segment_data = service.users().dataSources().datasets().get(userId='me', dataSourceId=ds_id, datasetId=dataset_id).execute()
            points = segment_data.get('point', [])
        except Exception:
            ds_id = "derived:com.google.sleep.segment:com.google.android.gms:merged"
            segment_data = service.users().dataSources().datasets().get(userId='me', dataSourceId=ds_id, datasetId=dataset_id).execute()
            points = segment_data.get('point', [])

        stage_names = {1: 'Awake', 4: 'Light', 5: 'Deep', 6: 'REM'}
        stages_by_day = {}

        for p in points:
            st = datetime.fromtimestamp(int(p['startTimeNanos'])/1e9)
            et = datetime.fromtimestamp(int(p['endTimeNanos'])/1e9)
            dur_sec = (et - st).total_seconds()
            st_val = p['value'][0]['intVal'] if p.get('value') else 0
            day_str = st.strftime('%Y-%m-%d')

            if day_str not in stages_by_day:
                stages_by_day[day_str] = {k: 0 for k in stage_names}
                stages_by_day[day_str]['total_sec'] = 0

            if st_val in stages_by_day[day_str]:
                stages_by_day[day_str][st_val] += dur_sec
                if st_val != 1:
                    stages_by_day[day_str]['total_sec'] += dur_sec

        sleep_stages_summary = {}
        for d, s in stages_by_day.items():
            tot = s['total_sec']
            sleep_stages_summary[d] = {
                "total_sleep_hours": round(tot / 3600, 2),
                "deep_sleep_min": round(s[5] / 60, 1),
                "deep_sleep_pct": round(s[5] / tot * 100, 1) if tot > 0 else 0,
                "rem_sleep_min": round(s[6] / 60, 1),
                "rem_sleep_pct": round(s[6] / tot * 100, 1) if tot > 0 else 0,
                "light_sleep_min": round(s[4] / 60, 1),
                "light_sleep_pct": round(s[4] / tot * 100, 1) if tot > 0 else 0,
                "awake_min": round(s[1] / 60, 1)
            }

        metrics_summary['sleep_stages_by_day'] = sleep_stages_summary
    except Exception as e:
        print(f"Error fetching sleep stages: {e}")

    # 3. Fetch Heart Rate
    try:
        dataset_id = f"{start_ns}-{end_ns}"
        data_source = "derived:com.google.heart_rate.bpm:com.google.android.gms:merge_heart_rate_bpm"
        hr_data = service.users().dataSources().datasets().get(userId='me', dataSourceId=data_source, datasetId=dataset_id).execute()
        
        bpm_values = []
        for point in hr_data.get('point', []):
            for val in point.get('value', []):
                if 'fpVal' in val:
                    bpm_values.append(val['fpVal'])
        
        if bpm_values:
            metrics_summary['heart_rate'] = {
                "avg_bpm": round(sum(bpm_values) / len(bpm_values), 1),
                "min_bpm": round(min(bpm_values), 1),
                "max_bpm": round(max(bpm_values), 1)
            }
    except Exception as e:
        print(f"Error fetching Heart Rate: {e}")

    # 4. Fetch SpO2 (Oxygen Saturation)
    try:
        dataset_id = f"{start_ns}-{end_ns}"
        ds_spo2 = "derived:com.google.oxygen_saturation:com.google.android.gms:merged"
        spo2_data = service.users().dataSources().datasets().get(userId='me', dataSourceId=ds_spo2, datasetId=dataset_id).execute()
        spo2_vals = []
        for p in (spo2_data.get('point') or []):
            for v in (p.get('value') or []):
                if 'fpVal' in v:
                    try:
                        val = float(v['fpVal'])
                        if val > 50.0:
                            spo2_vals.append(val)
                    except (ValueError, TypeError):
                        pass
        if spo2_vals:
            metrics_summary['spo2'] = {
                "avg_spo2": round(sum(spo2_vals) / len(spo2_vals), 1),
                "min_spo2": round(min(spo2_vals), 1),
                "max_spo2": round(max(spo2_vals), 1)
            }
    except Exception as e:
        print(f"Error fetching SpO2: {e}")

    # 5. Fetch Steps, Calories, Active Minutes
    try:
        dataset_id = f"{start_ns}-{end_ns}"
        steps_ds = "derived:com.google.step_count.delta:com.google.android.gms:estimated_steps"
        cals_ds = "derived:com.google.calories.expended:com.google.android.gms:merge_calories_expended"
        act_ds = "derived:com.google.active_minutes:com.google.android.gms:merge_active_minutes"

        steps_data = service.users().dataSources().datasets().get(userId='me', dataSourceId=steps_ds, datasetId=dataset_id).execute()
        cals_data = service.users().dataSources().datasets().get(userId='me', dataSourceId=cals_ds, datasetId=dataset_id).execute()
        act_data = service.users().dataSources().datasets().get(userId='me', dataSourceId=act_ds, datasetId=dataset_id).execute()

        total_steps = sum(v['intVal'] for p in steps_data.get('point', []) for v in p.get('value', []) if 'intVal' in v)
        total_cals = sum(v['fpVal'] for p in cals_data.get('point', []) for v in p.get('value', []) if 'fpVal' in v)
        total_active_min = sum(v['intVal'] for p in act_data.get('point', []) for v in p.get('value', []) if 'intVal' in v)

        metrics_summary['activity'] = {
            "total_steps": total_steps,
            "total_calories": round(total_cals, 1),
            "active_minutes": total_active_min
        }
    except Exception as e:
        print(f"Error fetching activity metrics: {e}")

    # Save summary record to SQLite
    conn = sqlite3.connect(DB_PATH)
    try:
        import sqlite_vec
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
    except Exception as ve:
        pass
    now_str = datetime.now().isoformat()
    record_id = f"google_fit_sync_{int(time.time())}"
    
    desc_str = f"Google Fit Enhanced Sync {now_str[:10]}: "
    if 'sleep_sessions' in metrics_summary:
        desc_str += f"Сессий сна: {len(metrics_summary['sleep_sessions'])}, Тренировок: {len(metrics_summary.get('workouts', []))}. "
    if 'activity' in metrics_summary:
        act = metrics_summary['activity']
        desc_str += f"Шаги: {act['total_steps']}, Калории: {act['total_calories']} ккал, Активность: {act['active_minutes']} мин. "

    conn.execute(
        "INSERT OR REPLACE INTO kg_nodes (id, name, domain, node_type, description, tags, properties) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            record_id,
            f"Расширенная сводка Google Fit ({now_str[:10]})",
            "health",
            "observation",
            desc_str,
            "google_fit,full_metrics,health_api,user_report,sessions_api",
            json.dumps(metrics_summary, ensure_ascii=False)
        )
    )
    conn.commit()
    conn.close()

    print("Enhanced fitness metrics (sessions, sleep stages, workouts, HR, SpO2) synced successfully!")
    return metrics_summary

if __name__ == "__main__":
    fetch_and_save_fitness_data()
