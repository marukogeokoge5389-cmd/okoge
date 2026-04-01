"""京都市体育館一括予約 Web アプリ"""

import logging
import threading
from flask import Flask, render_template, request, jsonify, session
from config import GYMNASIUMS, TIME_SLOTS, CHUSEN_FACILITIES, CHUSEN_TIME_SLOTS, CHUSEN_SPORTS
from reservation import KyotoGymReserver
from lottery import KyotoGymLottery

app = Flask(__name__)
app.secret_key = "kyoto-gym-reservation-secret-key-change-in-production"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("reservation.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# 予約処理の状態管理
reservation_status = {}
status_lock = threading.Lock()


@app.route("/")
def index():
    """メインページ"""
    return render_template(
        "index.html",
        gymnasiums=GYMNASIUMS,
        time_slots=TIME_SLOTS,
    )


@app.route("/lottery")
def lottery_page():
    """抽選申込ページ"""
    return render_template(
        "lottery.html",
        facilities=CHUSEN_FACILITIES,
        time_slots=CHUSEN_TIME_SLOTS,
        sports=CHUSEN_SPORTS,
    )


@app.route("/api/reserve", methods=["POST"])
def reserve():
    """一括予約APIエンドポイント"""
    data = request.get_json()

    user_code = data.get("user_code", "").strip()
    password = data.get("password", "").strip()
    reservations = data.get("reservations", [])

    if not user_code or not password:
        return jsonify({"error": "ユーザーコードとパスワードを入力してください"}), 400

    if not reservations:
        return jsonify({"error": "予約内容を設定してください"}), 400

    # 予約IDを生成
    import uuid
    reservation_id = str(uuid.uuid4())[:8]

    with status_lock:
        reservation_status[reservation_id] = {
            "status": "processing",
            "message": "予約処理を開始しています...",
            "results": [],
            "total": sum(len(r.get("time_slots", [])) for r in reservations),
            "completed": 0,
        }

    # バックグラウンドで予約処理を実行
    thread = threading.Thread(
        target=_run_reservation,
        args=(reservation_id, user_code, password, reservations),
    )
    thread.daemon = True
    thread.start()

    return jsonify({"reservation_id": reservation_id, "message": "予約処理を開始しました"})


def _run_reservation(reservation_id, user_code, password, reservations):
    """バックグラウンドで予約処理を実行"""
    reserver = KyotoGymReserver()

    try:
        with status_lock:
            reservation_status[reservation_id]["message"] = "ブラウザを起動中..."

        results = reserver.bulk_reserve(user_code, password, reservations)

        with status_lock:
            reservation_status[reservation_id].update({
                "status": "completed",
                "message": "予約処理が完了しました",
                "results": results,
                "completed": len(results),
            })

    except Exception as e:
        logger.error(f"予約処理エラー: {e}")
        with status_lock:
            reservation_status[reservation_id].update({
                "status": "error",
                "message": f"エラーが発生しました: {str(e)}",
            })


@app.route("/api/status/<reservation_id>")
def get_status(reservation_id):
    """予約処理の状態を取得"""
    with status_lock:
        status = reservation_status.get(reservation_id)

    if not status:
        return jsonify({"error": "予約IDが見つかりません"}), 404

    return jsonify(status)


@app.route("/api/lottery", methods=["POST"])
def lottery():
    """一括抽選申込APIエンドポイント"""
    data = request.get_json()

    user_code = data.get("user_code", "").strip()
    password = data.get("password", "").strip()
    applications = data.get("applications", [])

    if not user_code or not password:
        return jsonify({"error": "ユーザーコードとパスワードを入力してください"}), 400

    if not applications:
        return jsonify({"error": "抽選申込内容を設定してください"}), 400

    import uuid
    lottery_id = str(uuid.uuid4())[:8]

    with status_lock:
        reservation_status[lottery_id] = {
            "status": "processing",
            "message": "抽選申込処理を開始しています...",
            "results": [],
            "total": len(applications),
            "completed": 0,
        }

    thread = threading.Thread(
        target=_run_lottery,
        args=(lottery_id, user_code, password, applications),
    )
    thread.daemon = True
    thread.start()

    return jsonify({"reservation_id": lottery_id, "message": "抽選申込処理を開始しました"})


def _run_lottery(lottery_id, user_code, password, applications):
    """バックグラウンドで抽選申込処理を実行"""
    lottery = KyotoGymLottery()

    try:
        with status_lock:
            reservation_status[lottery_id]["message"] = "ブラウザを起動中..."

        results = lottery.bulk_apply(user_code, password, applications)

        with status_lock:
            reservation_status[lottery_id].update({
                "status": "completed",
                "message": "抽選申込処理が完了しました",
                "results": results,
                "completed": len(results),
            })

    except Exception as e:
        logger.error(f"抽選申込処理エラー: {e}")
        with status_lock:
            reservation_status[lottery_id].update({
                "status": "error",
                "message": f"エラーが発生しました: {str(e)}",
            })


@app.route("/api/gymnasiums")
def get_gymnasiums():
    """体育館一覧を取得"""
    return jsonify(GYMNASIUMS)


@app.route("/api/time_slots")
def get_time_slots():
    """時間帯一覧を取得"""
    return jsonify(TIME_SLOTS)


@app.route("/api/chusen_facilities")
def get_chusen_facilities():
    """抽選用施設一覧を取得"""
    return jsonify(CHUSEN_FACILITIES)


@app.route("/api/chusen_time_slots")
def get_chusen_time_slots():
    """抽選用時間帯一覧を取得"""
    return jsonify(CHUSEN_TIME_SLOTS)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
