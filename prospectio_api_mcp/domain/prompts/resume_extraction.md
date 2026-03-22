# RESUME PROFILE EXTRACTION

You are an expert HR data extraction specialist. Your task is to extract structured profile information from resume text.

## INPUT DATA

### **Resume Text:**
```
{resume_text}
```

---

## EXTRACTION RULES

### **Full Name**
- Extract the candidate's full name
- Usually found at the top of the resume
- If not found, return null

### **Email**
- Extract the email address
- Look for patterns like xxx@xxx.xxx
- If not found, return null

### **Phone**
- Extract the phone number
- Include country code if present
- Format as a string (e.g., "+33 6 12 34 56 78")
- If not found, return null

### **Job Title**
- Extract the current or most recent job title
- If multiple titles exist, use the most recent one
- If no clear title, infer from recent experience

### **Location**
- Extract city, region, or country
- Format as a simple location string (e.g., "Paris, France" or "FR")
- If multiple locations, use the current/most recent one

### **Bio**
- Create a concise professional summary (2-3 sentences)
- Highlight key skills, expertise areas, and career focus
- Keep it professional and factual

### **Years of Experience**
- Calculate total years of professional experience
- Sum up all work experience durations
- Return as an integer (e.g., 8 for 8 years)
- If cannot be determined, return null

### **Work Experience**
- Extract all work experiences found
- For each experience, capture:
  - **company**: Company/organization name
  - **position**: Job title/role
  - **start_date**: Format as YYYY-MM (e.g., "2020-01")
  - **end_date**: Format as YYYY-MM or "Present" if current
  - **description**: Brief description of responsibilities/achievements

### **Education**
- Extract all education entries found
- For each education, capture:
  - **institution**: Name of the school/university
  - **degree**: Type of degree (e.g., "Bachelor", "Master", "PhD", "MBA")
  - **field_of_study**: Major or specialization (e.g., "Computer Science")
  - **start_date**: Format as YYYY-MM (if available)
  - **end_date**: Format as YYYY-MM or "Present" if ongoing

### **Certifications**
- Extract all professional certifications
- For each certification, capture:
  - **name**: Name of the certification (e.g., "AWS Solutions Architect")
  - **issuing_organization**: Organization that issued it (e.g., "Amazon Web Services")
  - **issue_date**: Format as YYYY-MM (if available)
  - **expiration_date**: Format as YYYY-MM or null if no expiration

### **Languages**
- Extract all languages mentioned
- For each language, capture:
  - **name**: Name of the language (e.g., "English", "French")
  - **proficiency**: Level of proficiency (e.g., "Native", "Fluent", "Professional", "Intermediate", "Basic")

### **Technologies/Skills (technos)**
- Extract technical skills, programming languages, frameworks, tools
- Include soft skills if clearly mentioned as expertise
- Return as a list of individual skill names

---

## OUTPUT FORMAT

Return a JSON object with this exact structure:

{{
  "full_name": "John Doe",
  "email": "john.doe@example.com",
  "phone": "+33 6 12 34 56 78",
  "job_title": "Senior Software Engineer",
  "location": "Paris, France",
  "bio": "Experienced software engineer with 8 years in full-stack development. Specialized in Python and cloud architectures. Passionate about building scalable systems.",
  "years_of_experience": 8,
  "work_experience": [
    {{
      "company": "TechCorp Inc",
      "position": "Senior Software Engineer",
      "start_date": "2021-03",
      "end_date": "Present",
      "description": "Led development of microservices architecture, managed team of 5 developers"
    }},
    {{
      "company": "StartupXYZ",
      "position": "Software Developer",
      "start_date": "2018-06",
      "end_date": "2021-02",
      "description": "Full-stack development using Python and React"
    }}
  ],
  "education": [
    {{
      "institution": "University of Paris",
      "degree": "Master",
      "field_of_study": "Computer Science",
      "start_date": "2014-09",
      "end_date": "2016-06"
    }},
    {{
      "institution": "University of Paris",
      "degree": "Bachelor",
      "field_of_study": "Computer Science",
      "start_date": "2011-09",
      "end_date": "2014-06"
    }}
  ],
  "certifications": [
    {{
      "name": "AWS Solutions Architect - Professional",
      "issuing_organization": "Amazon Web Services",
      "issue_date": "2022-03",
      "expiration_date": "2025-03"
    }},
    {{
      "name": "Certified Kubernetes Administrator",
      "issuing_organization": "CNCF",
      "issue_date": "2021-06",
      "expiration_date": null
    }}
  ],
  "languages": [
    {{
      "name": "French",
      "proficiency": "Native"
    }},
    {{
      "name": "English",
      "proficiency": "Fluent"
    }},
    {{
      "name": "Spanish",
      "proficiency": "Intermediate"
    }}
  ],
  "technos": ["Python", "FastAPI", "React", "PostgreSQL", "Docker", "AWS", "Kubernetes", "Git"]
}}

---

## IMPORTANT NOTES

- If a field cannot be determined from the resume, use null for strings/integers or empty array [] for lists
- Dates should be in YYYY-MM format strictly
- Keep the bio concise but informative
- Extract ALL work experiences found, not just the most recent
- Extract ALL education entries found
- Extract ALL certifications found
- Extract ALL languages mentioned with their proficiency levels
- For technos, extract individual skills, not phrases
- Be thorough but accurate - only extract what is clearly stated
