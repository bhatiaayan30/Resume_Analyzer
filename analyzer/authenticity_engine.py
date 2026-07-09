import re
import datetime
import math
from collections import Counter

MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
}

AI_BUZZWORDS = {
    "delve": "AI-favored word / transition",
    "tapestry": "frequent AI metaphor",
    "testament": "typical AI-generated conclusion phrasing",
    "spearheaded": "highly overused bullet starter",
    "leverage": "corporate buzzword heavily favored by AI",
    "robust": "overused AI descriptor for code/systems",
    "synergy": "generic corporate jargon",
    "pioneered": "overused bullet starter",
    "streamlined": "overused optimization buzzword",
    "impactful": "AI filler adjective",
    "fostered": "common AI collaboration verb",
    "orchestrated": "overused tech execution verb",
    "cutting-edge": "generic AI marketing phrase",
    "revolutionized": "exaggerated resume claim",
    "multifaceted": "AI filler adjective"
}

def parse_single_date(s: str) -> datetime.date:
    """Helper to convert a partial date string into a datetime.date object."""
    if not s:
        return None
    s = s.strip().lower()
    if s in ['present', 'current', 'now', 'active', 'till date']:
        return datetime.date.today()
    
    # 1. Year only (e.g., "2021")
    year_match = re.fullmatch(r'(20\d{2}|19\d{2})', s)
    if year_match:
        return datetime.date(int(year_match.group(1)), 1, 1)
        
    # 2. Month Year (e.g., "June 2021", "06/2021", "06-2021")
    month_year_match = re.search(r'([a-z]+|[0-9]{1,2})[\s\/\-](20\d{2}|19\d{2})', s)
    if month_year_match:
        m_str, y_str = month_year_match.group(1), month_year_match.group(2)
        year = int(y_str)
        month = 1
        if m_str.isdigit():
            month = max(1, min(12, int(m_str)))
        elif m_str in MONTHS:
            month = MONTHS[m_str]
        return datetime.date(year, month, 1)
        
    # 3. Year Month (e.g., "2021-06", "2021/06")
    year_month_match = re.search(r'(20\d{2}|19\d{2})[\s\/\-]([a-z]+|[0-9]{1,2})', s)
    if year_month_match:
        y_str, m_str = year_month_match.group(1), year_month_match.group(2)
        year = int(y_str)
        month = 1
        if m_str.isdigit():
            month = max(1, min(12, int(m_str)))
        elif m_str in MONTHS:
            month = MONTHS[m_str]
        return datetime.date(year, month, 1)
        
    # Fallback to finding any 4-digit year
    any_year = re.search(r'(20\d{2}|19\d{2})', s)
    if any_year:
        return datetime.date(int(any_year.group(1)), 1, 1)
        
    return None

def parse_duration(duration_str: str):
    """Splits duration range like 'June 2021 - Dec 2023' into start/end dates."""
    if not duration_str or not isinstance(duration_str, str):
        return None, None
    parts = re.split(r'\s+to\s+|\s*-\s*|\s*–\s*|\s*—\s*', duration_str, maxsplit=1)
    if len(parts) == 2:
        start = parse_single_date(parts[0])
        end = parse_single_date(parts[1])
        return start, end
    elif len(parts) == 1:
        start = parse_single_date(parts[0])
        return start, start
    return None, None

def run_chronological_checks(experience: list) -> list:
    """Analyzes work history for date overlaps, gaps, and rapid seniority progression."""
    checks = []
    if not experience or not isinstance(experience, list):
        return checks

    parsed_roles = []
    for exp in experience:
        role = exp.get("role", "Unknown Role")
        company = exp.get("company", "Unknown Company")
        duration = exp.get("duration", "")
        start, end = parse_duration(duration)
        if start and end:
            parsed_roles.append({
                "role": role,
                "company": company,
                "start": start,
                "end": end,
                "duration_str": duration
            })

    # Sort parsed roles by start date descending (newest first)
    parsed_roles.sort(key=lambda x: x["start"], reverse=True)

    # 1. Overlap Check (Concurrent full-time jobs)
    non_conflicting_keywords = ["freelance", "intern", "part-time", "parttime", "contract", "consultant", "self-employed", "founder", "co-founder"]
    for i in range(len(parsed_roles)):
        for j in range(i + 1, len(parsed_roles)):
            r1, r2 = parsed_roles[i], parsed_roles[j]
            t1, t2 = r1["role"].lower(), r2["role"].lower()
            if any(k in t1 for k in non_conflicting_keywords) or any(k in t2 for k in non_conflicting_keywords):
                continue
                
            latest_start = max(r1["start"], r2["start"])
            earliest_end = min(r1["end"], r2["end"])
            if latest_start < earliest_end:
                overlap_days = (earliest_end - latest_start).days
                overlap_months = overlap_days // 30
                if overlap_months >= 2:
                    checks.append({
                        "status": "warning",
                        "issue": "Timeline Overlap",
                        "details": f"Concurrent experience detected: '{r1['role']}' ({r1['company']}) overlaps with '{r2['role']}' ({r2['company']}) by approximately {overlap_months} months."
                    })

    # 2. Employment Gap Check (>6 months gap between consecutive jobs)
    for i in range(len(parsed_roles) - 1):
        r_current = parsed_roles[i]
        r_previous = parsed_roles[i + 1]
        
        if r_current["start"] > r_previous["end"]:
            gap_days = (r_current["start"] - r_previous["end"]).days
            gap_months = gap_days // 30
            if gap_months >= 6:
                checks.append({
                    "status": "pass" if gap_months < 12 else "warning",
                    "issue": "Employment Gap",
                    "details": f"Gap of {gap_months} months detected between '{r_previous['role']}' at {r_previous['company']} and '{r_current['role']}' at {r_current['company']}."
                })

    # 3. Title Progression / Velocity Check (Rapid Seniority Progression)
    if parsed_roles:
        earliest_start = min(r["start"] for r in parsed_roles)
        latest_end = max(r["end"] for r in parsed_roles)
        career_years = (latest_end - earliest_start).days / 365.25
        
        senior_keywords = ["lead", "principal", "architect", "director", "vp", "head", "manager"]
        for r in parsed_roles:
            title = r["role"].lower()
            if any(k in title for k in senior_keywords):
                if career_years < 3.0:
                    checks.append({
                        "status": "warning",
                        "issue": "Rapid Seniority Progression",
                        "details": f"Title Velocity Audit: Candidate holds senior title '{r['role']}' with less than 3 years of total career history ({round(career_years, 1)} years). Verify credentials authenticity."
                    })
                    break

    return checks

def run_ai_phrasing_checks(text: str, experience: list = None) -> dict:
    """Programmatically detects AI signatures based on keyword density, length uniformity, and sentence structures."""
    if not text:
        return {"probability": 0, "evidence": []}
        
    text_lower = text.lower()
    evidence = []
    prob_scores = []
    
    # Heuristic 1: Keyword Density check
    total_buzzword_count = 0
    for word, reason in AI_BUZZWORDS.items():
        matches = len(re.findall(r'\b' + re.escape(word) + r'\b', text_lower))
        if matches > 0:
            total_buzzword_count += matches
            evidence.append(f"Stylistic Marker: Found AI-favored term '{word}' ({matches}x)")
            
    word_count = max(1, len(text_lower.split()))
    density = (total_buzzword_count / word_count) * 1000
    
    kw_prob = 5
    if word_count >= 100:
        if density > 12:
            kw_prob = 85
        elif density > 8:
            kw_prob = 65
        elif density > 4:
            kw_prob = 45
        elif density > 1:
            kw_prob = 25
        elif total_buzzword_count > 0:
            kw_prob = 15
    else:
        # For short text snippets (under 100 words), scale down probability to prevent false positive alerts
        if density > 12:
            kw_prob = 45
        elif total_buzzword_count > 0:
            kw_prob = 15
            
    prob_scores.append(kw_prob)

    # Gather experience bullets
    bullets = []
    if experience and isinstance(experience, list):
        for exp in experience:
            b_list = exp.get("bullets", [])
            if isinstance(b_list, list):
                bullets.extend([b.strip() for b in b_list if b.strip()])

    if len(bullets) >= 4:
        # Heuristic 2: Bullet Length Uniformity (Burstiness / Standard Deviation)
        word_counts = [len(b.split()) for b in bullets]
        mean = sum(word_counts) / len(word_counts)
        variance = sum((x - mean) ** 2 for x in word_counts) / len(word_counts)
        std_dev = math.sqrt(variance)
        
        # Only check/flag if average bullet word count is >= 8 to avoid flagging short, simple bullets
        if std_dev < 3.2 and mean >= 8:
            evidence.append(f"AI Style Signature: Hyper-uniform bullet point lengths (standard deviation of {round(std_dev, 1)} words). Organic human writing typically shows greater structural variation.")
            prob_scores.append(75 if std_dev < 2.0 else 55)

        # Heuristic 3: Grammatical Sentence Start Repetition
        ed_starts = 0
        for b in bullets:
            first_word = b.split()[0].rstrip(",.;:").lower() if b.split() else ""
            if first_word.endswith("ed") or first_word in ["led", "ran", "built", "wrote", "drew"]:
                ed_starts += 1
        
        verb_ratio = ed_starts / len(bullets)
        if verb_ratio >= 0.9:
            evidence.append(f"AI Formatting Signature: High density of verb-started bullet points ({round(verb_ratio * 100)}%). Typical templates lack organic sentence variety.")
            prob_scores.append(50)

    final_probability = max(prob_scores) if prob_scores else 5
    return {
        "probability": final_probability,
        "evidence": evidence
    }

def run_metrics_checks(experience: list, text: str = "") -> list:
    """Verifies if accomplishments are quantified and checks for repetitive metric placeholders."""
    checks = []
    if not experience or not isinstance(experience, list):
        return checks

    total_bullets = 0
    bullets_with_metrics = 0
    metric_regex = re.compile(r'\b\d+%?\b|\b\d+\s*(?:percent|million|billion|k|m|multiplier)\b|\$\s*\d+')

    for exp in experience:
        bullets = exp.get("bullets", [])
        if not isinstance(bullets, list):
            continue
            
        for b in bullets:
            total_bullets += 1
            if metric_regex.search(b):
                bullets_with_metrics += 1
                
                # Check for overly rounded or exaggerated claims e.g., "100%", "900%"
                perfect_metrics = re.findall(r'\b(\d00)%?\b', b)
                for pm in perfect_metrics:
                    if int(pm) >= 200:
                        checks.append({
                            "metric": pm + "% increase",
                            "credibility": "medium",
                            "critique": f"High rounded metric ({pm}%) found in '{exp.get('role')}'. Verify the baseline calculation for accuracy."
                        })

    # Heuristic 4: Repeated Metrics check (standard placeholders)
    if text:
        pcts = re.findall(r'\b(\d+)\s*%', text.lower())
        counts = Counter(pcts)
        for num, cnt in counts.items():
            if cnt >= 3 and int(num) in [10, 15, 20, 25, 30, 40, 50, 100]:
                checks.append({
                    "metric": f"{num}% repeated {cnt} times",
                    "credibility": "medium",
                    "critique": f"Metrics Audit: The percentage '{num}%' appears {cnt} times. This repetitive pattern frequently indicates template boilerplate values."
                })

    if total_bullets > 0:
        density = (bullets_with_metrics / total_bullets) * 100
        if density < 25:
            checks.append({
                "metric": f"Only {bullets_with_metrics} out of {total_bullets} bullets quantified",
                "credibility": "medium",
                "critique": f"Low metrics quantification density ({round(density)}%). Recruiter-optimized profiles should strive for at least 30-40% quantified impact points."
            })
            
    return checks

def audit_authenticity(resume_text: str, structured_resume: dict) -> dict:
    """Performs full programmatic scanning for AI signatures, chronological timeline, and metrics validation."""
    experience = structured_resume.get("experience", []) if isinstance(structured_resume, dict) else []
    
    ai_results = run_ai_phrasing_checks(resume_text, experience)
    chrono_results = run_chronological_checks(experience)
    metrics_results = run_metrics_checks(experience, resume_text)
    
    return {
        "ai_probability": ai_results["probability"],
        "ai_probability_evidence": ai_results["evidence"],
        "chronological_consistency": chrono_results,
        "metrics_credibility": metrics_results
    }
