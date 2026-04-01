"""京都市体育館予約サイト自動操作モジュール（お気に入り施設方式）

フロー:
  1. Login.cgi → txtRiyoshaCode / txtPassWord → isSubmitDataSet('Enter')
  2. ログイン後 → isNextFuncCodeSet('TopPageYoyaku') → お気に入り施設一覧
  3. oneClickSubmit('txtSelectKey','Enter','INDEX') → カレンダー(CalendarStatusSelect)
  4. 日付を「次の7日分」で送りつつ、checkYoyakuStatus チェックボックスを選択
     - value例: 261009_001_29_01_02_0201_20260420_1101
     - valueに日付(YYYYMMDD)が含まれる
  5. isSubmitDataSet('Enter') → 申込入力 → 内容確認 → 予約完了
"""

import time
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
    UnexpectedAlertPresentException,
)
from webdriver_manager.chrome import ChromeDriverManager
from config import BASE_URL, SELENIUM_TIMEOUT, HEADLESS_MODE, GYMNASIUMS, TIME_SLOTS

logger = logging.getLogger(__name__)


class KyotoGymReserver:
    def __init__(self, headless=None):
        self.driver = None
        self.wait = None
        self.headless = headless if headless is not None else HEADLESS_MODE
        self.logged_in = False

    # ── ブラウザ管理 ──

    def start_browser(self):
        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280,900")
        options.add_argument("--lang=ja-JP")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, SELENIUM_TIMEOUT)
        logger.info("ブラウザ起動")

    def close_browser(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.logged_in = False

    # ── ユーティリティ ──

    def _js(self, script, *args):
        return self.driver.execute_script(script, *args)

    def _dismiss_alert(self):
        """アラートがあれば閉じてテキストを返す"""
        try:
            alert = self.driver.switch_to.alert
            text = alert.text
            alert.accept()
            time.sleep(0.5)
            return text
        except Exception:
            return None

    def _screenshot_log(self, name):
        try:
            self.driver.save_screenshot(f"debug_{name}.png")
        except Exception:
            pass

    # ── Step 1: ログイン ──

    def login(self, user_code, password):
        try:
            self.driver.get(BASE_URL)
            time.sleep(3)
            self._dismiss_alert()

            result = self._js("""
                var uid = document.getElementById('txtRiyoshaCode');
                var pwd = document.getElementById('txtPassWord');
                var ok = {userId: false, password: false};
                if (uid) {
                    uid.value = arguments[0];
                    uid.dispatchEvent(new Event('input', {bubbles:true}));
                    uid.dispatchEvent(new Event('change', {bubbles:true}));
                    ok.userId = true;
                }
                if (pwd) {
                    pwd.value = arguments[1];
                    pwd.dispatchEvent(new Event('input', {bubbles:true}));
                    pwd.dispatchEvent(new Event('change', {bubbles:true}));
                    ok.password = true;
                }
                return JSON.stringify(ok);
            """, user_code, password)
            logger.info(f"ログインフィールド入力: {result}")
            time.sleep(0.5)

            self._js("isSubmitDataSet('Enter');")
            time.sleep(5)
            self._dismiss_alert()

            if "ログアウト" in self.driver.page_source:
                self.logged_in = True
                logger.info("ログイン成功")
                return {"success": True, "message": "ログイン成功"}

            self._screenshot_log("login_fail")
            return {"success": False, "message": "ログインに失敗しました"}

        except Exception as e:
            logger.error(f"ログインエラー: {e}")
            return {"success": False, "message": f"ログインエラー: {e}"}

    # ── Step 2: お気に入り施設一覧ページへ移動 ──

    def navigate_to_favorites(self):
        """「空き照会・予約」→ 検索条件ページ → 「★お気に入りから選択」→ お気に入り一覧"""
        try:
            # Step 2a: まず検索条件ページへ
            self._js("isNextFuncCodeSet('TopPageYoyaku');")
            time.sleep(4)
            self._dismiss_alert()

            current_url = self.driver.current_url
            logger.info(f"検索条件ページ遷移: URL={current_url}")

            # 既にお気に入りページにいる場合（2件目以降の予約等）
            has_fav = self._js("return document.querySelector('tr[onclick*=\"oneClickSubmit\"]') !== null;")
            if has_fav:
                logger.info("既にお気に入り施設一覧ページにいます")
                return True

            # Step 2b: 「★お気に入りから選択」ボタンをクリック
            clicked = self._js("""
                // ボタン/リンクのテキストで「お気に入り」を探す
                var targets = document.querySelectorAll('a, button, input[type="button"], label, li, div');
                for (var i = 0; i < targets.length; i++) {
                    var el = targets[i];
                    var text = (el.textContent || el.value || '').trim();
                    if (text.indexOf('お気に入り') >= 0 && text.length < 30) {
                        // onclick属性があればそれを使う
                        var onclick = el.getAttribute('onclick');
                        if (onclick) {
                            el.click();
                            return 'clicked: ' + text + ' (onclick=' + onclick.substring(0, 60) + ')';
                        }
                        // クリック可能な子要素を探す
                        var clickable = el.querySelector('a[onclick], button[onclick], [onclick]');
                        if (clickable) {
                            clickable.click();
                            return 'clicked child: ' + text;
                        }
                        // 要素自体をクリック
                        el.click();
                        return 'clicked element: ' + text + ' (tag=' + el.tagName + ')';
                    }
                }
                return false;
            """)
            logger.info(f"お気に入りボタン: {clicked}")

            if not clicked:
                # フォールバック: ラジオボタンの中にお気に入りオプションがある可能性
                clicked2 = self._js("""
                    var radios = document.querySelectorAll('input[type="radio"]');
                    for (var i = 0; i < radios.length; i++) {
                        var li = radios[i].closest('li') || radios[i].parentElement;
                        var text = li ? li.textContent.trim() : '';
                        if (text.indexOf('お気に入り') >= 0) {
                            radios[i].click();
                            return 'radio: ' + text + ' (id=' + radios[i].id + ')';
                        }
                    }
                    return false;
                """)
                logger.info(f"お気に入りラジオ: {clicked2}")
                if not clicked2:
                    self._screenshot_log("favorites_button_not_found")
                    logger.warning("お気に入りボタンが見つかりません")
                    return False

            time.sleep(4)
            self._dismiss_alert()

            # お気に入りページに遷移したか確認
            page_src = self.driver.page_source
            current_url = self.driver.current_url
            logger.info(f"お気に入り遷移後URL: {current_url}")

            has_fav = self._js("return document.querySelector('tr[onclick*=\"oneClickSubmit\"]') !== null;")
            if has_fav:
                logger.info("お気に入り施設一覧ページへ遷移成功")
                return True

            if "お気に入り" in page_src or "FavoriteSelect" in current_url:
                logger.info("お気に入りページ検出")
                return True

            self._screenshot_log("favorites_nav_fail")
            logger.warning("お気に入りページへの遷移に失敗")
            return False

        except Exception as e:
            logger.error(f"お気に入りページ遷移エラー: {e}")
            return False

    # ── Step 3: お気に入り施設を選択 ──

    def select_favorite_facility(self, fav_index):
        """お気に入りインデックスで施設を選択 → カレンダーページへ"""
        try:
            # 施設名をログに残す
            fav_name = self._js(f"""
                var rows = document.querySelectorAll('tr[onclick*="oneClickSubmit"]');
                if ({fav_index} < rows.length) {{
                    return rows[{fav_index}].textContent.trim().replace(/\\s+/g, ' ').substring(0, 60);
                }}
                return 'NOT FOUND';
            """)
            logger.info(f"お気に入り施設[{fav_index}]: {fav_name}")

            self._js(f"oneClickSubmit('txtSelectKey','Enter','{fav_index}');")
            time.sleep(4)
            self._dismiss_alert()

            current_url = self.driver.current_url
            page_src = self.driver.page_source
            logger.info(f"施設選択後URL: {current_url}")

            if "CalendarStatus" in current_url or "予約対象区分選択" in page_src:
                logger.info("カレンダーページへ遷移成功")
                return True

            self._screenshot_log("facility_select_fail")
            return False

        except Exception as e:
            logger.error(f"施設選択エラー: {e}")
            return False

    # ── Step 4: カレンダーで日付を合わせて空き時間帯を選択 ──

    def select_time_slots_on_calendar(self, target_date, time_slot_keys):
        """カレンダーページで「表示開始日」を変更→「選択した条件で表示」→ チェックボックス選択"""
        try:
            time.sleep(2)
            dt = datetime.strptime(target_date, "%Y-%m-%d")
            date_str = dt.strftime("%Y%m%d")       # "20260424"
            date_slash = dt.strftime("%Y/%m/%d")    # "2026/04/24"
            header_text = f"{dt.month}月{dt.day}日"  # "4月24日"

            target_slots_labels = [TIME_SLOTS.get(k, k) for k in time_slot_keys]
            logger.info(f"カレンダー検索: 日付={target_date} ({date_str}), 時間帯={target_slots_labels}")

            # まず現在のカレンダーに対象日付が含まれているか確認
            # ページソースでは「5月23日」の直後に曜日が付くため、YYYYMMDD形式で判定
            page_src = self.driver.page_source
            if date_str not in page_src:
                # 「表示開始日」を目的の日付に変更して「選択した条件で表示」
                logger.info(f"対象日付 {date_str} が未表示。31日間表示に切替＋開始日を {date_slash} に変更します")

                # 31日間表示に切替（id=31day ラジオボタン）
                self._js("""
                    var r = document.getElementById('31day');
                    if (r) r.checked = true;
                """)

                set_result = self._js("""
                    // 表示開始日 (id=startDate が既知)
                    var dateInput = document.getElementById('startDate')
                                 || document.querySelector('input[type="date"]');
                    if (!dateInput) {
                        var inputs = document.querySelectorAll('input');
                        for (var i = 0; i < inputs.length; i++) {
                            var v = inputs[i].value || '';
                            if (/^\\d{4}[\\/-]\\d{2}[\\/-]\\d{2}$/.test(v)) {
                                dateInput = inputs[i];
                                break;
                            }
                        }
                    }
                    if (dateInput) {
                        var oldVal = dateInput.value;
                        if (dateInput.type === 'date') {
                            dateInput.value = arguments[0].replace(/\\//g, '-');
                        } else {
                            dateInput.value = arguments[0];
                        }
                        dateInput.dispatchEvent(new Event('input', {bubbles:true}));
                        dateInput.dispatchEvent(new Event('change', {bubbles:true}));
                        return 'changed: ' + oldVal + ' -> ' + dateInput.value;
                    }
                    return false;
                """, date_slash)
                logger.info(f"表示開始日変更: {set_result}")

                if not set_result:
                    logger.warning("表示開始日フィールドが見つかりません")
                    self._screenshot_log("date_field_not_found")
                    return False

                # 「選択した条件で表示する」ボタン (isSubmitDataSet('Setup'))
                self._js("isSubmitDataSet('Setup');")
                time.sleep(5)
                self._dismiss_alert()

                # 再確認（YYYYMMDD形式で検索）
                page_src = self.driver.page_source
                if date_str not in page_src:
                    logger.warning(f"表示更新後も対象日付 {date_str} ({header_text}) が見つかりません")
                    self._screenshot_log("calendar_date_not_found")
                    return False

            logger.info(f"対象日付 {date_str} ({header_text}) がカレンダーに表示されています")

            # チェックボックスを選択
            # checkYoyakuStatus の value に日付(YYYYMMDD)が含まれる
            # 時間帯はテーブルの行ヘッダー(th)のテキストで判定
            selected_count = self._js("""
                var dateStr = arguments[0];       // "20260420"
                var targetSlots = arguments[1];   // ["09:00 - 10:00", ...]
                var selected = 0;

                var cbs = document.querySelectorAll('input[type="checkbox"][name="checkYoyakuStatus"]');
                for (var i = 0; i < cbs.length; i++) {
                    var cb = cbs[i];
                    if (cb.value.indexOf(dateStr) < 0) continue;

                    var tr = cb.closest('tr');
                    if (!tr) continue;
                    var th = tr.querySelector('th');
                    var timeText = th ? th.textContent.trim() : '';

                    for (var s = 0; s < targetSlots.length; s++) {
                        if (timeText === targetSlots[s] ||
                            timeText.replace(/ /g,'') === targetSlots[s].replace(/ /g,'') ||
                            timeText.indexOf(targetSlots[s]) >= 0 ||
                            targetSlots[s].indexOf(timeText) >= 0) {
                            if (!cb.checked && !cb.disabled) {
                                cb.click();
                                selected++;
                            }
                            break;
                        }
                    }
                }
                return selected;
            """, date_str, target_slots_labels)

            logger.info(f"チェックボックス選択数: {selected_count}")

            if selected_count > 0:
                self._screenshot_log("calendar_selected")
                return True

            self._screenshot_log("calendar_no_vacancy")
            logger.warning(f"空き枠なし: {target_date} {target_slots_labels}")
            return False

        except Exception as e:
            logger.error(f"カレンダー選択エラー: {e}")
            self._screenshot_log("calendar_error")
            return False

    # ── Step 5: 「選択した区分で次へ進む」 ──

    def click_proceed(self):
        try:
            self._js("isSubmitDataSet('Enter');")
            time.sleep(4)
            self._dismiss_alert()
            logger.info("「選択した区分で次へ進む」クリック")
            return True
        except Exception as e:
            logger.error(f"次へ進むエラー: {e}")
            return False

    # ── Step 6: 申込入力 & 確認 ──

    def submit_application(self):
        """申込入力 → 内容確認 → 予約完了"""
        try:
            for step in range(5):
                time.sleep(3)
                self._dismiss_alert()

                page_src = self.driver.page_source
                current_url = self.driver.current_url
                logger.info(f"申込ステップ {step}: URL={current_url}")

                # 予約完了判定
                if "予約完了" in page_src or "申込が完了" in page_src or "受付番号" in page_src:
                    logger.info("予約完了!")
                    self._screenshot_log("reservation_complete")
                    return True

                # 利用目的selectがあれば選択
                self._js("""
                    var selects = document.querySelectorAll('select');
                    for (var i = 0; i < selects.length; i++) {
                        if (selects[i].options.length > 1 && selects[i].selectedIndex <= 0) {
                            selects[i].selectedIndex = 1;
                            selects[i].dispatchEvent(new Event('change', {bubbles:true}));
                        }
                    }
                """)

                # 次に進むボタンを探してクリック
                btn_texts = ["申込む", "申込", "予約する", "確定", "次へ", "確認", "送信", "登録"]
                clicked = self._js("""
                    var targets = arguments[0];
                    var btns = document.querySelectorAll('button, input[type="button"], input[type="submit"]');
                    for (var t = 0; t < targets.length; t++) {
                        for (var i = 0; i < btns.length; i++) {
                            var text = (btns[i].textContent || btns[i].value || '').trim();
                            if (text.indexOf(targets[t]) >= 0) {
                                btns[i].click();
                                return text;
                            }
                        }
                    }
                    // onclick属性を持つa要素も検索
                    var links = document.querySelectorAll('a[onclick]');
                    for (var t = 0; t < targets.length; t++) {
                        for (var j = 0; j < links.length; j++) {
                            var lt = links[j].textContent.trim();
                            if (lt.indexOf(targets[t]) >= 0) {
                                links[j].click();
                                return lt;
                            }
                        }
                    }
                    return false;
                """, btn_texts)

                if clicked:
                    logger.info(f"ボタン「{clicked}」クリック (step {step})")
                    time.sleep(3)
                    self._dismiss_alert()
                else:
                    self._screenshot_log(f"submit_step{step}")
                    logger.warning(f"申込ボタンが見つかりません (step {step})")
                    break

            # 最終確認
            page_src = self.driver.page_source
            if "予約完了" in page_src or "受付番号" in page_src or "申込が完了" in page_src:
                return True

            self._screenshot_log("submit_final")
            return False

        except Exception as e:
            logger.error(f"申込エラー: {e}")
            return False

    # ── メイン: 1件の予約 ──

    def _reserve_single(self, gym_name, date, time_slot_keys):
        """1件の予約を実行"""
        result = {
            "gym": gym_name,
            "date": date,
            "time_slot": ", ".join(time_slot_keys),
            "success": False,
            "message": "",
        }

        try:
            fav_index = GYMNASIUMS.get(gym_name)
            if fav_index is None:
                result["message"] = f"施設 '{gym_name}' がお気に入りに登録されていません"
                return result

            # Step 2: お気に入りページへ
            if not self.navigate_to_favorites():
                result["message"] = "お気に入りページへの移動に失敗"
                return result

            # Step 3: 施設選択
            if not self.select_favorite_facility(fav_index):
                result["message"] = "施設の選択に失敗"
                return result

            # Step 4: カレンダーで時間帯選択
            if not self.select_time_slots_on_calendar(date, time_slot_keys):
                result["message"] = "空き枠が見つかりません（予約済み or 利用不可）"
                return result

            # Step 5: 次へ進む
            if not self.click_proceed():
                result["message"] = "「次へ進む」に失敗"
                return result

            # Step 6: 申込 → 確認 → 完了
            if self.submit_application():
                result["success"] = True
                result["message"] = "予約が完了しました"
            else:
                result["message"] = "申込確定に失敗（要手動確認）"

        except Exception as e:
            result["message"] = f"エラー: {e}"
            logger.error(f"予約エラー [{gym_name} {date}]: {e}")

        return result

    # ── メイン: 一括予約 ──

    def bulk_reserve(self, user_code, password, reservations):
        """一括予約"""
        results = []

        try:
            self.start_browser()

            login_result = self.login(user_code, password)
            if not login_result["success"]:
                return [
                    {"gym": r["gym"], "date": r["date"],
                     "time_slot": ", ".join(r.get("time_slots", [])),
                     "success": False, "message": login_result["message"]}
                    for r in reservations
                ]

            for res in reservations:
                result = self._reserve_single(
                    res["gym"], res["date"], res["time_slots"]
                )
                results.append(result)
                logger.info(f"結果: {result}")

        except Exception as e:
            logger.error(f"一括予約エラー: {e}")
            results.append({
                "gym": "", "date": "", "time_slot": "",
                "success": False, "message": f"システムエラー: {e}",
            })
        finally:
            self.close_browser()

        return results
