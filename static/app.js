const form = document.querySelector("#question-form");
const questionInput = document.querySelector("#question");
const answerCard = document.querySelector("#answer-card");
const answerTitle = document.querySelector("#answer-title");
const answerText = document.querySelector("#answer-text");
const sourceList = document.querySelector("#source-list");
const errorMessage = document.querySelector("#error-message");
const submitButton = form.querySelector("button");

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    answerCard.hidden = true;
    errorMessage.hidden = true;
    submitButton.disabled = true;
    submitButton.textContent = "Asking…";

    try {
        const response = await fetch("/api/ask", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                question: questionInput.value,
            }),
        });

        if (!response.ok) {
            throw new Error("Atlas could not answer the question.");
        }

        const result = await response.json();

        answerTitle.textContent = result.title;
        answerText.textContent = result.answer;

        sourceList.replaceChildren();

        for (const source of result.sources) {
            const item = document.createElement("li");
            item.textContent = source;
            sourceList.appendChild(item);
        }

        answerCard.hidden = false;
    } catch (error) {
        errorMessage.textContent = error.message;
        errorMessage.hidden = false;
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = "Ask";
    }
});