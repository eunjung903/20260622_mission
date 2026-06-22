const keywordInput = document.getElementById("keyword");
const generateBtn = document.getElementById("generateBtn");
const emailInput = document.getElementById("email");
const sendBtn = document.getElementById("sendBtn");
const statusEl = document.getElementById("status");
const reportSection = document.getElementById("reportSection");
const emailSection = document.getElementById("emailSection");
const reportTitle = document.getElementById("reportTitle");
const articleCount = document.getElementById("articleCount");
const reportContent = document.getElementById("reportContent");

let currentReport = "";
let currentKeyword = "";

function showStatus(message, type = "info") {
  statusEl.textContent = message;
  statusEl.className = `status ${type}`;
  statusEl.classList.remove("hidden");
}

function hideStatus() {
  statusEl.classList.add("hidden");
}

function setLoading(button, loading) {
  const text = button.querySelector(".btn-text");
  const spinner = button.querySelector(".spinner");
  button.disabled = loading;
  text.classList.toggle("hidden", loading);
  spinner.classList.toggle("hidden", !loading);
}

async function sendEmailViaFormSubmit(email, keyword, report) {
  const response = await fetch(`https://formsubmit.co/ajax/${encodeURIComponent(email)}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      _subject: `[AI 뉴스 리포터] '${keyword}' 보고서`,
      _captcha: "false",
      message: report,
    }),
  });

  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error("이메일 발송 응답을 확인할 수 없습니다.");
  }

  if (String(data.success).toLowerCase() === "true") {
    return "발송이 완료되었습니다";
  }

  const message = data.message || "";
  if (message.toLowerCase().includes("activat")) {
    return (
      "활성화 링크를 이메일로 보냈습니다. 수신함에서 'Activate Form' 링크를 " +
      "클릭한 후 다시 [발송]을 눌러 주세요."
    );
  }

  throw new Error(message || "이메일 발송에 실패했습니다.");
}

generateBtn.addEventListener("click", async () => {
  const keyword = keywordInput.value.trim();
  if (!keyword) {
    showStatus("키워드를 입력해 주세요.", "error");
    return;
  }

  hideStatus();
  setLoading(generateBtn, true);
  reportSection.classList.add("hidden");
  emailSection.classList.add("hidden");

  try {
    showStatus("Gemini로 최근 2일 내 기사를 검색하고 있습니다...", "info");

    const response = await fetch("/api/generate-report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keyword }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "보고서 생성에 실패했습니다.");
    }

    currentReport = data.report;
    currentKeyword = data.keyword;

    reportTitle.textContent = `'${data.keyword}' 뉴스 보고서`;
    articleCount.textContent = `${data.article_count}건 수집`;
    reportContent.innerHTML = marked.parse(data.report);

    reportSection.classList.remove("hidden");
    emailSection.classList.remove("hidden");
    hideStatus();
  } catch (err) {
    showStatus(err.message, "error");
  } finally {
    setLoading(generateBtn, false);
  }
});

sendBtn.addEventListener("click", async () => {
  const email = emailInput.value.trim();
  if (!email) {
    showStatus("이메일 주소를 입력해 주세요.", "error");
    return;
  }

  if (!currentReport) {
    showStatus("먼저 보고서를 생성해 주세요.", "error");
    return;
  }

  setLoading(sendBtn, true);

  try {
    showStatus("이메일을 발송하고 있습니다...", "info");

    let message;
    try {
      message = await sendEmailViaFormSubmit(email, currentKeyword, currentReport);
    } catch (clientError) {
      const response = await fetch("/api/send-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          keyword: currentKeyword,
          report: currentReport,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || clientError.message || "이메일 발송에 실패했습니다.");
      }
      message = data.message;
    }

    alert(message);
    showStatus(message, message.includes("활성화") ? "info" : "success");
  } catch (err) {
    showStatus(err.message, "error");
  } finally {
    setLoading(sendBtn, false);
  }
});

keywordInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") generateBtn.click();
});

emailInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendBtn.click();
});
