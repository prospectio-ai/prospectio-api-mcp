import os

class PromptLoader:
    prompt_mapping = {
        "compatibility_score": "../prompts/compatibility_score.md",
        "company_decision": "../prompts/company_decision.md",
        "company_description": "../prompts/company_description.md",
        "company_info": "../prompts/company_info.md",
        "contact_bio": "../prompts/contact_bio.md",
        "contact_info": "../prompts/contact_info.md",
        "contacts_from_answer": "../prompts/contacts_from_answer.md",
        "job_titles": "../prompts/job_titles.md",
        "prospecting_message": "../prompts/prospecting_message.md",
        "resume_extraction": "../prompts/resume_extraction.md",
    }

    def load_prompt(self, chat_profile: str) -> str:
        prompt_path = os.path.join(
            os.path.dirname(__file__),
            f"{self.prompt_mapping.get(chat_profile)}",
        )
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            return "You are a helpful AI assistant."
