"""京都市体育館 抽選申込自動操作モジュール

フロー:
  1. Login.cgi → ログイン
  2. isNextFuncCodeSet('TopPageChusen') → グループ選択ページ
  3. setOptSearchItemChusenGroup('CODE','NAME') + checkSearchValueSubmit('Search')
     → 施設絞り込み（場所選択）
  4. checkMeisaiUniqKey チェックボックス選択 + isSubmitDataSet('Enter')
     → 抽選申込対象区分選択（カレンダー）
  5. checkYoyakuStatus チェックボックス選択 + isSubmitDataSet('Enter')
     → 申込内容確認（フォーム入力）
     - value例: 261009_001_29_01_02_0201_20260502_1101
  6. フォーム入力(練習/バドミントン/16人) + isSubmitDataSet('Enter')
     → 抽選申込完了
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
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from config import (
    BASE_URL, SELENIUM_TIMEOUT, HEADLESS_MODE,
    CHUSEN_GROUPS, CHUSEN_FACILITIES, CHUSEN_TIME_SLOTS,
    CHUSEN_FIXED_PARAMS, CHUSEN_SPORTS,
)

logger = logging.getLogger(__name__)


class KyotoGymLottery:
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
        logger.info("ブラウザ起動（抽選）")

    def close_browser(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.logged_in = False

    # ── ユーティリティ ──

    def _js(self, script, *args):
        return self.driver.execute_script(script, *args)

    def _dismiss_alert(self):
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
            self.driver.save_screenshot(f"debug_chusen_{name}.png")
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

    # ── Step 2: 抽選申込グループ選択ページへ ──

    def navigate_to_chusen(self):
        """抽選申込トップ（グループ選択）ページへ移動"""
        try:
            self._js("isNextFuncCodeSet('TopPageChusen');")
            time.sleep(4)
            self._dismiss_alert()

            current_url = self.driver.current_url
            page_src = self.driver.page_source
            logger.info(f"抽選トップ遷移: URL={current_url}")

            if "jouken2" in current_url or "抽選" in page_src:
                logger.info("抽選グループ選択ページへ遷移成功")
                return True

            self._screenshot_log("chusen_nav_fail")
            return False

        except Exception as e:
            logger.error(f"抽選ページ遷移エラー: {e}")
            return False

    # ── Step 3: グループ選択 → 施設絞り込みページ ──

    def select_group(self, group_name):
        """グループコードで施設グループを選択"""
        try:
            group_code = CHUSEN_GROUPS.get(group_name)
            if not group_code:
                logger.error(f"グループ '{group_name}' が設定にありません")
                return False

            # setOptSearchItemChusenGroup('CODE', 'NAME') + checkSearchValueSubmit('Search')
            self._js(f"""
                setOptSearchItemChusenGroup('{group_code}', '京都市 {group_name}');
                checkSearchValueSubmit('Search');
            """)
            time.sleep(4)
            self._dismiss_alert()

            current_url = self.driver.current_url
            page_src = self.driver.page_source
            logger.info(f"グループ選択後URL: {current_url}")

            if "施設絞り込み" in page_src or "checkMeisaiUniqKey" in page_src:
                logger.info(f"施設絞り込みページへ遷移成功: {group_name}")
                return True

            self._screenshot_log("group_select_fail")
            return False

        except Exception as e:
            logger.error(f"グループ選択エラー: {e}")
            return False

    # ── Step 4: 施設選択 ──

    def select_facility(self, facility_code):
        """チェックボックスで施設を選択して次へ"""
        try:
            selected = self._js("""
                var code = arguments[0];
                var cbs = document.querySelectorAll('input[name="checkMeisaiUniqKey"]');
                for (var i = 0; i < cbs.length; i++) {
                    if (cbs[i].value === code) {
                        cbs[i].checked = true;
                        return cbs[i].value;
                    }
                }
                return false;
            """, facility_code)

            if not selected:
                logger.error(f"施設コード {facility_code} が見つかりません")
                self._screenshot_log("facility_not_found")
                return False

            logger.info(f"施設選択: {selected}")

            # 「選択した施設で検索」ボタン
            self._js("isSubmitDataSet('Enter');")
            time.sleep(4)
            self._dismiss_alert()

            page_src = self.driver.page_source
            current_url = self.driver.current_url
            logger.info(f"施設選択後URL: {current_url}")

            if "ChusenMultiSelect" in current_url or "対象区分選択" in page_src:
                logger.info("抽選カレンダーページへ遷移成功")
                return True

            self._screenshot_log("facility_select_fail")
            return False

        except Exception as e:
            logger.error(f"施設選択エラー: {e}")
            return False

    # ── Step 5: カレンダーで日付・時間帯を選択 ──

    def select_time_slots_on_calendar(self, target_date, time_slot_keys):
        """カレンダーページで「表示開始日」を変更→「選択した条件で表示」→ チェックボックス選択"""
        try:
            time.sleep(2)
            dt = datetime.strptime(target_date, "%Y-%m-%d")
            date_str = dt.strftime("%Y%m%d")       # "20260502"
            date_slash = dt.strftime("%Y/%m/%d")    # "2026/05/02"
            header_text = f"{dt.month}月{dt.day}日"

            # 時間帯コードに変換
            target_time_codes = []
            for key in time_slot_keys:
                code = CHUSEN_TIME_SLOTS.get(key)
                if code:
                    target_time_codes.append(code)
                else:
                    logger.warning(f"不明な時間帯キー: {key}")

            logger.info(f"カレンダー検索: 日付={target_date} ({date_str}), "
                        f"時間帯コード={target_time_codes}")

            # まず現在のカレンダーに対象日付が含まれているか確認
            # ページソースでは「5月23日」の直後に曜日が付く（例: "5月23日\n土"）ため
            # checkYoyakuStatus の value に日付文字列(YYYYMMDD)が含まれるかで判定する
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
                    // 表示開始日の入力フィールドを探す (id=startDate が既知)
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
                        // type="date" → YYYY-MM-DD 形式
                        if (dateInput.type === 'date') {
                            dateInput.value = arguments[0].replace(/\\//g, '-');
                        } else {
                            dateInput.value = arguments[0];
                        }
                        dateInput.dispatchEvent(new Event('input', {bubbles:true}));
                        dateInput.dispatchEvent(new Event('change', {bubbles:true}));
                        return 'changed: ' + oldVal + ' -> ' + dateInput.value + ' (id=' + dateInput.id + ')';
                    }
                    return false;
                """, date_slash)
                logger.info(f"表示開始日変更: {set_result}")

                if not set_result:
                    logger.warning("表示開始日フィールドが見つかりません")
                    self._screenshot_log("date_field_not_found")
                    return {"selected": 0, "message": "表示開始日フィールドが見つかりません"}

                # 「選択した条件で表示する」ボタン (isSubmitDataSet('Setup'))
                self._js("isSubmitDataSet('Setup');")
                time.sleep(5)
                self._dismiss_alert()

                # カレンダー日付範囲をログ出力
                current_range = self._js("""
                    var ths = document.querySelectorAll('th');
                    var dates = [];
                    for (var i = 0; i < ths.length; i++) {
                        var t = ths[i].textContent.trim();
                        if (/^\\d+月\\d+日/.test(t)) dates.push(t.split('\\n')[0]);
                    }
                    return dates.join(', ');
                """)
                logger.info(f"表示更新後のカレンダー範囲: {current_range}")

                # 再確認（YYYYMMDD形式で検索）
                page_src = self.driver.page_source
                if date_str not in page_src:
                    logger.warning(f"表示更新後も対象日付 {date_str} ({header_text}) が見つかりません")
                    self._screenshot_log("calendar_date_not_found")
                    return {"selected": 0, "message": f"対象日付 {header_text} が見つかりません（表示範囲外）"}

            logger.info(f"対象日付 {date_str} ({header_text}) がカレンダーに表示されています")

            # チェックボックスを選択（下側カレンダーのみから選択）
            # checkYoyakuStatus value: 施設コード_0201_YYYYMMDD_時間コード
            # ページに上下2つのカレンダーがある場合、下側（2番目）のテーブルから選択する
            selected_count = self._js("""
                var dateStr = arguments[0];
                var timeCodes = arguments[1];
                var selected = 0;

                // 全チェックボックスを取得
                var allCbs = document.querySelectorAll('input[type="checkbox"][name="checkYoyakuStatus"]');
                if (allCbs.length === 0) return 0;

                // チェックボックスが属するテーブルを特定し、ユニークなテーブル一覧を取得
                var tables = [];
                var tableSet = new Set();
                for (var i = 0; i < allCbs.length; i++) {
                    var tbl = allCbs[i].closest('table');
                    if (tbl && !tableSet.has(tbl)) {
                        tableSet.add(tbl);
                        tables.push(tbl);
                    }
                }

                // 下側（最後の）テーブルを対象とする。テーブルが1つなら唯一のものを使う
                var targetTable = tables[tables.length - 1];

                // 対象テーブル内のチェックボックスのみ取得
                var cbs = targetTable.querySelectorAll('input[type="checkbox"][name="checkYoyakuStatus"]');
                for (var i = 0; i < cbs.length; i++) {
                    var val = cbs[i].value;
                    // valueに日付が含まれるか
                    if (val.indexOf(dateStr) < 0) continue;

                    // valueの末尾が時間帯コードにマッチするか
                    for (var t = 0; t < timeCodes.length; t++) {
                        if (val.endsWith('_' + timeCodes[t])) {
                            if (!cbs[i].checked && !cbs[i].disabled) {
                                cbs[i].click();
                                selected++;
                            }
                            break;
                        }
                    }
                }
                return selected;
            """, date_str, target_time_codes)

            logger.info(f"チェックボックス選択数: {selected_count}")

            if selected_count > 0:
                self._screenshot_log("calendar_selected")
                return {"selected": selected_count, "message": "OK"}

            self._screenshot_log("calendar_no_vacancy")
            return {"selected": 0, "message": "申込可能な枠がありません"}

        except Exception as e:
            logger.error(f"カレンダー選択エラー: {e}")
            self._screenshot_log("calendar_error")
            return {"selected": 0, "message": f"エラー: {e}"}

    # ── Step 6: 「選択した区分で次へ進む」 ──

    def click_proceed(self):
        try:
            self._js("isSubmitDataSet('Enter');")
            time.sleep(4)
            self._dismiss_alert()

            page_src = self.driver.page_source
            current_url = self.driver.current_url
            logger.info(f"次へ進む後URL: {current_url}")

            if "KubunSelect" in current_url or "申込内容" in page_src or "行事名称" in page_src:
                logger.info("申込入力ページへ遷移成功")
                return True

            self._screenshot_log("proceed_fail")
            return False

        except Exception as e:
            logger.error(f"次へ進むエラー: {e}")
            return False

    # ── Step 7: 申込フォーム入力 & 確定 ──

    def fill_and_submit_application(self, sport="バドミントン"):
        """申込フォームに固定値を入力して確定"""
        try:
            sport_info = CHUSEN_SPORTS.get(sport, CHUSEN_SPORTS["バドミントン"])
            params = {
                **CHUSEN_FIXED_PARAMS,
                "gyojiName": sport_info["gyojiName"],
                "genreSmall": sport_info["genreSmall"],
            }

            # フォーム入力
            result = self._js("""
                var p = arguments[0];
                var filled = {};

                // 行事名称（利用目的）
                var mokuteki = document.getElementById('cmbRiyoMokuteki');
                if (mokuteki) {
                    mokuteki.value = p.riyoMokuteki;
                    mokuteki.dispatchEvent(new Event('change', {bubbles:true}));
                    filled.riyoMokuteki = mokuteki.value;
                }

                // 備考（行事名）
                var gyoji = document.getElementById('txtGyojiName');
                if (gyoji) {
                    gyoji.value = p.gyojiName;
                    gyoji.dispatchEvent(new Event('input', {bubbles:true}));
                    filled.gyojiName = gyoji.value;
                }

                // ジャンル
                var genre = document.getElementById('cmbGenreSmall');
                if (genre) {
                    genre.value = p.genreSmall;
                    genre.dispatchEvent(new Event('change', {bubbles:true}));
                    filled.genreSmall = genre.value;
                }

                // 入場者数
                var count = document.getElementById('txtNyujoCount');
                if (count) {
                    count.value = p.nyujoCount;
                    count.dispatchEvent(new Event('input', {bubbles:true}));
                    filled.nyujoCount = count.value;
                }

                return JSON.stringify(filled);
            """, params)
            logger.info(f"フォーム入力結果: {result}")

            time.sleep(1)

            # 「申込内容確定」ボタン
            self._js("isSubmitDataSet('Enter');")
            time.sleep(5)
            self._dismiss_alert()

            page_src = self.driver.page_source
            current_url = self.driver.current_url
            logger.info(f"確定後URL: {current_url}")

            # 完了判定
            if "申込完了" in page_src or "受け付けました" in page_src or "抽選申込番号" in page_src:
                # 抽選申込番号を取得
                chusen_no = self._js("""
                    var text = document.body.innerText;
                    var match = text.match(/抽選申込番号[：:]\\s*(\\S+)/);
                    return match ? match[1] : '';
                """) or ""
                logger.info(f"抽選申込完了！ 番号: {chusen_no}")
                self._screenshot_log("chusen_complete")
                return {"success": True, "message": f"抽選申込完了 (番号: {chusen_no})", "chusen_no": chusen_no}

            self._screenshot_log("submit_fail")
            return {"success": False, "message": "申込確定に失敗（要手動確認）"}

        except Exception as e:
            logger.error(f"申込フォームエラー: {e}")
            return {"success": False, "message": f"エラー: {e}"}

    # ── 1件の抽選申込 ──

    def _apply_single(self, facility_name, date, time_slot_keys, sport="バドミントン"):
        """1件の抽選申込を実行（sportは各申込ごとに指定）"""
        result = {
            "facility": facility_name,
            "date": date,
            "time_slots": ", ".join(time_slot_keys),
            "success": False,
            "message": "",
        }

        try:
            facility_code = CHUSEN_FACILITIES.get(facility_name)
            if not facility_code:
                result["message"] = f"施設 '{facility_name}' が設定にありません"
                return result

            # グループ名を施設名から判定
            group_name = None
            for gname in CHUSEN_GROUPS:
                if gname in facility_name:
                    group_name = gname
                    break
            if not group_name:
                result["message"] = f"施設 '{facility_name}' のグループが特定できません"
                return result

            # Step 2: 抽選トップへ
            if not self.navigate_to_chusen():
                result["message"] = "抽選ページへの移動に失敗"
                return result

            # Step 3: グループ選択
            if not self.select_group(group_name):
                result["message"] = "グループ選択に失敗"
                return result

            # Step 4: 施設選択
            if not self.select_facility(facility_code):
                result["message"] = "施設選択に失敗"
                return result

            # Step 5: カレンダーで時間帯選択
            cal_result = self.select_time_slots_on_calendar(date, time_slot_keys)
            if cal_result["selected"] == 0:
                result["message"] = cal_result["message"]
                return result

            # Step 6: 次へ進む
            if not self.click_proceed():
                result["message"] = "「次へ進む」に失敗"
                return result

            # Step 7: フォーム入力 & 確定
            submit_result = self.fill_and_submit_application(sport=sport)
            result["success"] = submit_result["success"]
            result["message"] = submit_result["message"]

        except Exception as e:
            result["message"] = f"エラー: {e}"
            logger.error(f"抽選申込エラー [{facility_name} {date}]: {e}")

        return result

    # ── 一括抽選申込 ──

    def bulk_apply(self, user_code, password, applications):
        """一括抽選申込"""
        results = []

        try:
            self.start_browser()

            login_result = self.login(user_code, password)
            if not login_result["success"]:
                return [
                    {"facility": a["facility"], "date": a["date"],
                     "time_slots": ", ".join(a.get("time_slots", [])),
                     "success": False, "message": login_result["message"]}
                    for a in applications
                ]

            for app in applications:
                res = self._apply_single(
                    app["facility"], app["date"], app["time_slots"],
                    sport=app.get("sport", "バドミントン"),
                )
                results.append(res)
                logger.info(f"抽選結果: {res}")

        except Exception as e:
            logger.error(f"一括抽選エラー: {e}")
            results.append({
                "facility": "", "date": "", "time_slots": "",
                "success": False, "message": f"システムエラー: {e}",
            })
        finally:
            self.close_browser()

        return results
