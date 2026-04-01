document.addEventListener("DOMContentLoaded", () => {
    const lotteryList = document.getElementById("lottery-list");
    const addBtn = document.getElementById("add-lottery-btn");
    const executeBtn = document.getElementById("execute-btn");
    const resultSection = document.getElementById("result-section");
    const resultList = document.getElementById("result-list");
    const progressBarContainer = document.getElementById("progress-bar-container");
    const progressFill = document.getElementById("progress-fill");
    const progressText = document.getElementById("progress-text");
    const totalCountEl = document.getElementById("total-count");
    const template = document.getElementById("lottery-template");

    let entryCount = 0;

    // 日本の祝日リスト（2026-2027年）
    const HOLIDAYS = [
        // 2026
        "2026-01-01", "2026-01-12", "2026-02-11", "2026-02-23",
        "2026-03-20", "2026-04-29", "2026-05-03", "2026-05-04",
        "2026-05-05", "2026-05-06", "2026-07-20", "2026-08-11",
        "2026-09-21", "2026-09-23", "2026-10-12", "2026-11-03",
        "2026-11-23",
        // 2027
        "2027-01-01", "2027-01-11", "2027-02-11", "2027-02-23",
        "2027-03-21", "2027-03-22", "2027-04-29", "2027-05-03",
        "2027-05-04", "2027-05-05", "2027-07-19", "2027-08-11",
        "2027-09-20", "2027-09-23", "2027-10-11", "2027-11-03",
        "2027-11-23",
    ];
    const holidaySet = new Set(HOLIDAYS);

    function isWeekendOrHoliday(dateStr) {
        const d = new Date(dateStr + "T00:00:00");
        const day = d.getDay();
        return day === 0 || day === 6 || holidaySet.has(dateStr);
    }

    function getAvailableFacilities(sport) {
        const sportData = SPORT_FACILITIES[sport];
        return sportData ? sportData.facilities : [];
    }

    function updateFacilitySelect(selectEl, sport) {
        const currentVal = selectEl.value;
        const facilities = getAvailableFacilities(sport);
        selectEl.innerHTML = '<option value="">-- 体育館を選択 --</option>';
        facilities.forEach((name) => {
            const opt = document.createElement("option");
            opt.value = name;
            opt.textContent = name;
            selectEl.appendChild(opt);
        });
        if (facilities.includes(currentVal)) {
            selectEl.value = currentVal;
        } else if (facilities.length === 1) {
            // 施設が1つだけなら自動選択
            selectEl.value = facilities[0];
        }
    }

    function getLastEntry() {
        const entries = lotteryList.querySelectorAll(".lottery-entry");
        if (entries.length === 0) return null;
        return entries[entries.length - 1];
    }

    // 初期エントリを1つ追加
    addEntry();

    addBtn.addEventListener("click", addEntry);
    executeBtn.addEventListener("click", executeLottery);

    function addEntry() {
        entryCount++;
        const clone = template.content.cloneNode(true);
        const entry = clone.querySelector(".lottery-entry");
        entry.dataset.index = entryCount;
        entry.querySelector(".entry-number").textContent = entryCount;

        const sportSelect = entry.querySelector(".sport-select");
        const facilitySelect = entry.querySelector(".facility-select");
        const dateInput = entry.querySelector(".date-input");

        // 前のエントリから競技・日付・体育館を引き継ぎ
        const lastEntry = getLastEntry();
        if (lastEntry) {
            const prevSport = lastEntry.querySelector(".sport-select").value;
            const prevFacility = lastEntry.querySelector(".facility-select").value;
            const prevDate = lastEntry.querySelector(".date-input").value;

            sportSelect.value = prevSport;
            updateFacilitySelect(facilitySelect, prevSport);
            facilitySelect.value = prevFacility;
            if (prevDate) {
                dateInput.value = prevDate;
            }
        } else {
            // 初回: デフォルト1ヶ月後の直近土日祝を設定
            updateFacilitySelect(facilitySelect, sportSelect.value);
            const nextMonth = new Date();
            nextMonth.setMonth(nextMonth.getMonth() + 1);
            const dateStr = findNextWeekendOrHoliday(nextMonth);
            dateInput.value = dateStr;
        }

        // 競技変更 → 施設リスト更新
        sportSelect.addEventListener("change", () => {
            updateFacilitySelect(facilitySelect, sportSelect.value);
            updateCount();
        });

        // 日付変更 → 土日祝チェック
        dateInput.addEventListener("change", () => {
            if (dateInput.value && !isWeekendOrHoliday(dateInput.value)) {
                alert("土日祝日のみ選択できます");
                const d = new Date(dateInput.value + "T00:00:00");
                dateInput.value = findNextWeekendOrHoliday(d);
            }
            updateCount();
        });

        // 削除ボタン
        entry.querySelector(".remove-entry-btn").addEventListener("click", () => {
            entry.remove();
            updateCount();
            renumberEntries();
        });

        // 変更監視
        entry.querySelectorAll("select, input").forEach((el) => {
            el.addEventListener("change", updateCount);
        });

        lotteryList.appendChild(entry);
        updateCount();
    }

    function findNextWeekendOrHoliday(fromDate) {
        const d = new Date(fromDate);
        for (let i = 0; i < 14; i++) {
            const str = d.toISOString().slice(0, 10);
            if (isWeekendOrHoliday(str)) return str;
            d.setDate(d.getDate() + 1);
        }
        // 見つからなければそのまま返す
        return fromDate.toISOString().slice(0, 10);
    }

    function renumberEntries() {
        const entries = lotteryList.querySelectorAll(".lottery-entry");
        entries.forEach((entry, i) => {
            entry.querySelector(".entry-number").textContent = i + 1;
        });
    }

    function updateCount() {
        let total = 0;
        const entries = lotteryList.querySelectorAll(".lottery-entry");
        entries.forEach((entry) => {
            const facility = entry.querySelector(".facility-select").value;
            const date = entry.querySelector(".date-input").value;
            const slots = entry.querySelectorAll(".time-slot-checkbox input:checked");
            if (facility && date && slots.length > 0) {
                total += 1;
            }
        });
        totalCountEl.textContent = total;
        executeBtn.disabled = total === 0;
    }

    function collectApplications() {
        const applications = [];
        const entries = lotteryList.querySelectorAll(".lottery-entry");

        entries.forEach((entry) => {
            const sport = entry.querySelector(".sport-select").value;
            const facility = entry.querySelector(".facility-select").value;
            const date = entry.querySelector(".date-input").value;
            const slots = [];
            entry.querySelectorAll(".time-slot-checkbox input:checked").forEach((cb) => {
                slots.push(cb.value);
            });

            if (facility && date && slots.length > 0) {
                applications.push({
                    sport: sport,
                    facility: facility,
                    date: date,
                    time_slots: slots,
                });
            }
        });

        return applications;
    }

    async function executeLottery() {
        const userCode = document.getElementById("user-code").value.trim();
        const password = document.getElementById("password").value.trim();

        if (!userCode || !password) {
            alert("ユーザーコードとパスワードを入力してください");
            return;
        }

        const applications = collectApplications();
        if (applications.length === 0) {
            alert("抽選申込内容を設定してください");
            return;
        }

        if (!confirm(`${applications.length}件の抽選申込を実行しますか？`)) {
            return;
        }

        // UI更新
        executeBtn.disabled = true;
        executeBtn.textContent = "処理中...";
        resultSection.classList.remove("hidden");
        progressBarContainer.classList.remove("hidden");
        resultList.innerHTML = "";
        progressFill.style.width = "0%";
        progressText.textContent = "抽選申込処理を開始しています...";

        try {
            const response = await fetch("/api/lottery", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_code: userCode,
                    password: password,
                    applications: applications,
                }),
            });

            const data = await response.json();

            if (data.error) {
                progressText.textContent = data.error;
                resetButton();
                return;
            }

            pollStatus(data.reservation_id, applications.length);
        } catch (err) {
            progressText.textContent = `エラー: ${err.message}`;
            resetButton();
        }
    }

    async function pollStatus(lotteryId, totalCount) {
        const interval = setInterval(async () => {
            try {
                const response = await fetch(`/api/status/${lotteryId}`);
                const data = await response.json();

                if (data.error) {
                    clearInterval(interval);
                    progressText.textContent = data.error;
                    resetButton();
                    return;
                }

                const pct = totalCount > 0
                    ? Math.round((data.completed / totalCount) * 100)
                    : 0;
                progressFill.style.width = `${pct}%`;
                progressText.textContent = data.message;

                if (data.status === "completed" || data.status === "error") {
                    clearInterval(interval);
                    progressFill.style.width = "100%";
                    displayResults(data.results || []);
                    resetButton();
                }
            } catch (err) {
                clearInterval(interval);
                progressText.textContent = `通信エラー: ${err.message}`;
                resetButton();
            }
        }, 2000);
    }

    function displayResults(results) {
        resultList.innerHTML = "";

        if (results.length === 0) {
            resultList.innerHTML = '<p style="text-align:center;color:#666;">結果がありません</p>';
            return;
        }

        let successCount = 0;
        let failCount = 0;

        results.forEach((r) => {
            const item = document.createElement("div");
            const isSuccess = r.success;
            item.className = `result-item ${isSuccess ? "success" : "failure"}`;

            if (isSuccess) successCount++;
            else failCount++;

            const slotLabel = r.time_slots || "";
            item.innerHTML = `
                <span class="result-icon">${isSuccess ? "&#10003;" : "&#10007;"}</span>
                <div class="result-detail">
                    <strong>${r.facility || "不明"} - ${r.date || ""} ${slotLabel}</strong>
                    <span>${r.message || ""}</span>
                </div>
            `;
            resultList.appendChild(item);
        });

        const summary = document.createElement("div");
        summary.style.cssText = "text-align:center;padding:16px;margin-top:12px;font-weight:600;";
        summary.textContent = `結果: ${successCount}件成功 / ${failCount}件失敗 (合計${results.length}件)`;
        resultList.appendChild(summary);
    }

    function resetButton() {
        executeBtn.disabled = false;
        executeBtn.textContent = "一括抽選申込を実行";
    }
});
