"""抽選申込モジュールの単体テスト
使い方: python test_lottery.py <ユーザーコード> <パスワード>
※最後の申込送信は行いません（安全テスト）
"""
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("test_lottery.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

from lottery import KyotoGymLottery


def test_lottery(user_code, password, submit=False):
    """抽選申込の一連の流れをテスト"""
    lottery = KyotoGymLottery()
    results = []

    def step(name, func):
        logger.info(f"=== {name} ===")
        try:
            result = func()
            if result:
                logger.info(f"OK: {name}")
                results.append((name, "OK", result))
                return result
            else:
                logger.error(f"FAIL: {name}")
                results.append((name, "FAIL", result))
                return None
        except Exception as e:
            logger.error(f"ERROR: {name} - {e}")
            results.append((name, "ERROR", str(e)))
            return None

    try:
        lottery.start_browser()

        # Step 1: ログイン
        login_result = step("ログイン", lambda: lottery.login(user_code, password))
        if not login_result or not login_result.get("success"):
            logger.error("ログイン失敗。テスト中断。")
            return results

        # Step 2: 抽選トップへ
        if not step("抽選トップ遷移", lottery.navigate_to_chusen):
            return results

        # Step 3: グループ選択
        if not step("グループ選択(醍醐地域体育館)", lambda: lottery.select_group("醍醐地域体育館")):
            return results

        # Step 4: 施設選択
        if not step("施設選択(1/2面)", lambda: lottery.select_facility("261009_001_29_01_02")):
            return results

        # Step 5: カレンダー日付・時間帯選択
        cal_result = step(
            "カレンダー選択(5/20 11:00-13:00)",
            lambda: lottery.select_time_slots_on_calendar("2026-05-20", ["11:00-13:00"])
        )
        if not cal_result or cal_result.get("selected", 0) == 0:
            logger.error(f"カレンダー選択失敗: {cal_result}")
            return results

        # Step 6: 次へ進む
        if not step("次へ進む", lottery.click_proceed):
            return results

        # Step 7: フォーム確認
        page_src = lottery.driver.page_source
        if "行事名称" in page_src or "cmbRiyoMokuteki" in page_src:
            logger.info("OK: 申込フォームページに到達")
            results.append(("申込フォーム到達", "OK", ""))
            lottery._screenshot_log("test_form_reached")

            if submit:
                submit_result = step("申込送信", lottery.fill_and_submit_application)
                logger.info(f"送信結果: {submit_result}")
            else:
                logger.info("申込送信はスキップ（--submit オプションで実行可能）")
        else:
            logger.error("FAIL: 申込フォームページに到達していない")
            results.append(("申込フォーム到達", "FAIL", ""))
            lottery._screenshot_log("test_form_fail")

    except Exception as e:
        logger.error(f"テストエラー: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # テスト結果サマリー
        logger.info("\n" + "=" * 50)
        logger.info("テスト結果サマリー")
        logger.info("=" * 50)
        for name, status, detail in results:
            mark = "OK" if status == "OK" else "NG"
            logger.info(f"  [{mark}] {name}")
        logger.info("=" * 50)

        time.sleep(3)
        lottery.close_browser()

    return results


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("使い方: python test_lottery.py <ユーザーコード> <パスワード> [--submit]")
        print("  --submit: 実際に申込を送信する（省略時は送信しない）")
        sys.exit(1)

    user_code = sys.argv[1]
    password = sys.argv[2]
    do_submit = "--submit" in sys.argv

    test_lottery(user_code, password, submit=do_submit)
