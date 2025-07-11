import docx
import re
from collections import Counter
import spacy
from typing import Dict, List, Tuple

# Load English language model for spaCy
nlp = spacy.load("en_core_web_sm")

def extract_email(text):
    """Extract email address from text"""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    match = re.search(email_pattern, text)
    return match.group(0) if match else None

def extract_skills(text):
    """Extract skills from resume text using spaCy"""
    doc = nlp(text)
    skills = []
    
    # Common skills to look for
    common_skills = {
        'python', 'java', 'javascript', 'c++', 'c#', 'sql', 'html', 'css',
        'react', 'angular', 'vue', 'node.js', 'django', 'flask', 'spring',
        'aws', 'azure', 'docker', 'kubernetes', 'git', 'linux', 'machine learning',
        'data analysis', 'project management', 'agile', 'scrum'
    }
    
    # Extract nouns and noun phrases that might represent skills
    for chunk in doc.noun_chunks:
        lower_chunk = chunk.text.lower()
        if any(skill in lower_chunk for skill in common_skills):
            skills.append(chunk.text)
    
    # Also check individual tokens
    for token in doc:
        if token.text.lower() in common_skills and token.text.lower() not in [s.lower() for s in skills]:
            skills.append(token.text)
    
    return list(set(skills))[:15]  # Return unique skills, max 15

def calculate_ats_score(text, job_description=None):
    """
    Calculate ATS (Applicant Tracking System) compatibility score
    This is a simplified version - in reality, ATS algorithms are more complex
    """
    score = 50  # Base score
    
    # Check for important sections
    sections = ['experience', 'education', 'skills', 'projects']
    found_sections = sum(1 for section in sections if section in text.lower())
    score += found_sections * 5
    
    # Check length (ideal is 1-2 pages)
    word_count = len(text.split())
    if 300 <= word_count <= 800:  # Rough estimate for 1-2 pages
        score += 10
    elif word_count > 800:
        score -= 5
    
    # Check for action verbs
    action_verbs = ['managed', 'led', 'developed', 'created', 'implemented', 
                   'designed', 'improved', 'increased', 'reduced', 'optimized']
    found_verbs = sum(1 for verb in action_verbs if verb in text.lower())
    score += min(found_verbs, 10)  # Max 10 points for verbs
    
    return min(max(score, 0), 100)  # Ensure score is between 0-100

def match_job_role(text):
    """Match resume text to common job roles"""
    roles = {
        'Software Engineer': ['software', 'developer', 'programmer', 'coding', 'algorithm'],
        'Data Scientist': ['data science', 'machine learning', 'ai', 'statistics', 'python'],
        'Web Developer': ['web', 'javascript', 'html', 'css', 'frontend', 'backend'],
        'DevOps Engineer': ['devops', 'aws', 'azure', 'docker', 'kubernetes', 'ci/cd'],
        'Project Manager': ['project management', 'agile', 'scrum', 'leadership', 'team']
    }
    
    text_lower = text.lower()
    matches = {}
    
    for role, keywords in roles.items():
        matches[role] = sum(1 for keyword in keywords if keyword in text_lower)
    
    if not any(matches.values()):
        return "General", 0
    
    best_match = max(matches.items(), key=lambda x: x[1])
    match_percentage = (best_match[1] / len(roles[best_match[0]])) * 100
    return best_match[0], min(round(match_percentage), 100)

def generate_suggestions(text):
    """Generate suggestions to improve the resume"""
    suggestions = []
    text_lower = text.lower()
    
    # Check for common issues
    if 'objective' in text_lower and 'summary' not in text_lower:
        suggestions.append("Consider replacing 'Objective' with a 'Professional Summary'")
    
    if not any(verb in text_lower for verb in ['achieved', 'improved', 'increased', 'reduced']):
        suggestions.append("Add more action verbs and quantifiable achievements")
    
    if len(text.split()) < 300:
        suggestions.append("Your resume seems too short - consider adding more details")
    elif len(text.split()) > 800:
        suggestions.append("Your resume seems too long - consider trimming to 1-2 pages")
    
    if not any(section in text_lower for section in ['skills', 'technical skills']):
        suggestions.append("Add a dedicated 'Skills' section")
    
    if len(suggestions) == 0:
        suggestions.append("Your resume looks good! Consider tailoring it for specific job applications")
    
    return suggestions[:5]  # Return max 5 suggestions

def parse_resume(filepath):
    """Main function to parse a DOCX resume"""
    try:
        doc = docx.Document(filepath)
        full_text = "\n".join([para.text for para in doc.paragraphs])
        
        email = extract_email(full_text)
        skills = extract_skills(full_text)
        ats_score = calculate_ats_score(full_text)
        job, match_score = match_job_role(full_text)
        suggestions = generate_suggestions(full_text)
        
        return {
            'email': email,
            'skills': skills,
            'ats_score': ats_score,
            'job': job,
            'match_score': match_score,
            'suggestions': suggestions
        }
        
    except Exception as e:
        print(f"Error parsing resume: {str(e)}")
        return {
            'email': None,
            'skills': [],
            'ats_score': 0,
            'job': "Unknown",
            'match_score': 0,
            'suggestions': ["Error processing resume"]
        }