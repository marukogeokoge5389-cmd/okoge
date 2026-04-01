document.addEventListener("DOMContentLoaded", () => {
    const reservationList = document.getElementById("reservation-list");
    const addBtn = document.getElementById("add-reservation-btn");
    const executeBtn = document.getElementById("execute-btn");
    const resultSection = document.getElementById("result-section");
    const resultList = document.getElementById("result-list");
    const progressBarContainer = document.getElementById("progress-bar-container");
    const progressFill = document.getElementById("progress-fill");
    const progressText = document.getElementById("progress-text");
    const totalCountEl = document.getElementById("total-count");
    const template = document.getElementById("reservation-template");

    let entryCount = 0;

    // 初期エントリを1つ追加
    addEntry();

    // 予約追加ボタン
    addBtn.addEventListener("click", addEntry);

    // 実行ボタン
    executeBtn.addEventListener("click", executeReservation);

    function addEntry() {
        entryCount++;
        const clone = template.content.cloneNode(true);
        const entry = clone.querySelector(".reservation-entry");
        entry.dataset.index = entryCount;
        entry.querySelector(".entry-number").textContent = entryCount;

        // 日付のデフォルトを明日に設定
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        const dateInput = entry.querySelector(".date-input");
        dateInput.valueAsDate = tomorrow;

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

        reservationList.appendChild(entry);
        updateCount();
    }

    function renumberEntries() {
        const entries = reservationList.querySelectorAll(".reservation-entry");
        entries.forEach((entry, i) => {
            entry.querySelector(".entry-number").textContent = i + 1;
        });
    }

    function updateCount() {
        let total = 0;
        const entries = reservationList.querySelectorAll(".reservation-entry");
        entries.forEach((entry) => {
            const gym = entry.querySelector(".gym-select").value;
            const date = entry.querySelector(".date-input").value;
            const slots = entry.querySelectorAll(
                ".time-slot-checkbox input:checked"
            );
            if (gym && date && slots.length > 0) {
                total += slots.length;
            }
        });
        totalCountEl.textContent = total;
        executeBtn.disabled = total === 0;
    }

    function collectReservations() {
        const reservations = [];
        const entries = reservationList.querySelectorAll(".reservation-entry");

        entries.forEach((entry) => {
            const gym = entry.querySelector(".gym-select").value;
            const date = entry.querySelector(".date-input").value;
            const slots = [];
            entry
                .querySelectorAll(".time-slot-checkbox input:checked")
                .forEach((cb) => {
                    slots.push(cb.value);
                });

            if (gym && date && slots.length > 0) {
                reservations.push({
                    gym: gym,
                    date: date,
                    time_slots: slots,
                });
            }
        });

        return reservations;
    }

    async function executeReservation() {
        const userCode = document.getElementById("user-code").value.trim();
        const password = document.getElementById("password").value.trim();

        if (!userCode || !password) {
            alert("ユーザーコードとパスワードを入力してください");
            return;
        }

        const reservations = collectReservations();
        if (reservations.length === 0) {
            alert("予約内容を設定してください");
            return;
        }

        // 確認ダイアログ
        const totalSlots = reservations.reduce(
            (sum, r) => sum + r.time_slots.length,
            0
        );
        if (
            !confirm(
                `${reservations.length}施設・${totalSlots}コマの予約を実行しますか？`
            )
        ) {
            return;
        }

        // UI更新
        executeBtn.disabled = true;
        executeBtn.textContent = "処理中...";
        resultSection.classList.remove("hidden");
        progressBarContainer.classList.remove("hidden");
        resultList.innerHTML = "";
        progressFill.style.width = "0%";
        progressText.textContent = "予約処理を開始しています...";

        try {
            const response = await fetch("/api/reserve", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_code: userCode,
                    password: password,
                    reservations: reservations,
                }),
            });

            const data = await response.json();

            if (data.error) {
                progressText.textContent = data.error;
                executeBtn.disabled = false;
                executeBtn.textContent = "一括予約を実行";
                return;
            }

            // ポーリングで状態を監視
            pollStatus(data.reservation_id, totalSlots);
        } catch (err) {
            progressText.textContent = `エラー: ${err.message}`;
            executeBtn.disabled = false;
            executeBtn.textContent = "一括予約を実行";
        }
    }

    async function pollStatus(reservationId, totalSlots) {
        const interval = setInterval(async () => {
            try {
                const response = await fetch(`/api/status/${reservationId}`);
                const data = await response.json();

                if (data.error) {
                    clearInterval(interval);
                    progressText.textContent = data.error;
                    resetButton();
                    return;
                }

                // 進捗更新
                const pct =
                    totalSlots > 0
                        ? Math.round((data.completed / totalSlots) * 100)
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
            resultList.innerHTML =
                '<p style="text-align:center;color:#666;">結果がありません</p>';
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

            const slotLabel = r.time_slot || "";
            item.innerHTML = `
                <span class="result-icon">${isSuccess ? "&#10003;" : "&#10007;"}</span>
                <div class="result-detail">
                    <strong>${r.gym || "不明"} - ${r.date || ""} ${slotLabel}</strong>
                    <span>${r.message || ""}</span>
                </div>
            `;
            resultList.appendChild(item);
        });

        // サマリー
        const summary = document.createElement("div");
        summary.style.cssText =
            "text-align:center;padding:16px;margin-top:12px;font-weight:600;";
        summary.textContent = `結果: ${successCount}件成功 / ${failCount}件失敗 (合計${results.length}件)`;
        resultList.appendChild(summary);
    }

    function resetButton() {
        executeBtn.disabled = false;
        executeBtn.textContent = "一括予約を実行";
    }
});
