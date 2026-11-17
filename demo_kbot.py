from brd_agent import brd_generator

project = {
    "project_name": "KBOT AI",
    "organization": "Internal Functions",
    "industry": "Technology",
    "project_type": "AI / GenAI project",
    "sponsor": "Head of Digital Enablement",
    "prepared_by": "Smriti Raman",
    "reviewed_by": "Engagement Manager",
    "version": "1.0",
    "doc_date": "2026-07-27",
    "start_date": "2026-08-01",
    "end_date": "2027-02-28",
    "description": (
        "A generative AI powered chat bot supporting HR, IR, ICOE and TAX-DPP "
        "by enabling a conversational way for employees to access policy related "
        "information."
    ),
}

answers = {
    # --- 8 existing questions ---
    "q_problem": (
        "Employees must read lengthy policy documents or chase department SPOCs "
        "for routine queries, which is slow and inconsistent.\n"
        "Employee raises query to department SPOC\n"
        "SPOC searches policy documents manually\n"
        "SPOC responds over email or Teams\n"
        "No audit trail of responses"
    ),
    "q_objective": (
        "Employees get instant, accurate, context-aware answers to policy "
        "questions without contacting a SPOC.\n"
        "Reduce SPOC query volume by 60% and response time from 2 days to "
        "under 1 minute."
    ),
    "q_inscope": (
        "HR policy queries\n"
        "IR policy queries\n"
        "ICOE and TAX-DPP document Q&A\n"
        "Leave balance and eligibility lookups"
    ),
    "q_outscope": (
        "Payroll transaction processing\n"
        "Performance management workflows\n"
        "Any external or client-facing deployment"
    ),
    "q_users": (
        "Employee\n"
        "Department SPOC\n"
        "Policy administrator\n"
        "System administrator"
    ),
    "q_features": (
        "Conversational Q&A over policy documents\n"
        "Summarised answers spanning multiple documents\n"
        "Personalised responses using employee demographics\n"
        "Leave balance check and eligibility validation\n"
        "Location-specific holiday list\n"
        "Query volume dashboard\n"
        "Unanswered-query report\n"
        "Retrieval augmented generation over the central policy repository"
    ),
    "q_systems": (
        "SharePoint\n"
        "HRMS\n"
        "Azure AD\n"
        "Microsoft Teams"
    ),
    "q_regs": (
        "DPDP Act 2023 for employee personal data; internal information "
        "security policy."
    ),
    # --- 3 new questions (inference derives all detail fields from these) ---
    "q_tech": (
        "Cloud deployment on Azure.\n"
        "Users access via desktop browser and Microsoft Teams bot.\n"
        "Policy documents stored in SharePoint, read via Graph API.\n"
        "Employee demographics via HRMS REST API over TLS 1.2.\n"
        "Data exchange in JSON format.\n"
        "Email notifications via SMTP for admin alerts."
    ),
    "q_security": (
        "Azure AD SSO with SAML for all users.\n"
        "MFA enforced for administrator and policy administrator roles.\n"
        "Full audit trail of all queries and bot responses retained for "
        "12 months.\n"
        "All data must remain resident in India."
    ),
    "q_nonfunc": (
        "Response within 5 seconds for 95% of queries.\n"
        "99.5% uptime during business hours (9 AM to 7 PM IST).\n"
        "RPO 24 hours, RTO 8 hours.\n"
        "Support up to 500 concurrent users at peak.\n"
        "Handle up to 10,000 queries per day."
    ),
}

# detail dict is EMPTY -- inference.py fills all 16 fields automatically
detail = {}

tables = [{
    "id": "open_items",
    "name": "Open Item List",
    "cols": [
        "Agenda", "Current Status", "Description",
        "Owner/Stakeholder Responsible",
        "Expected date of closure", "Impact if not Closed",
        "Remarks if any",
    ],
    "rows": [[
        "Demographics data access", "In discussion",
        "HRMS API scope for DOJ/DOB fields", "HR Tech Lead",
        "15 Aug 2026", "Personalisation cannot be delivered", "",
    ]],
}]

s = brd_generator.build(project, answers, detail, tables, "outputs")
print(f"File:       {s['filename']}")
print(f"Grounding:  {s['grounding_pct']}%")
print(f"Readiness:  {s['readiness']}")
print(f"Open gaps:  {s['open_gaps']} ({s['high_priority_gaps']} high priority)")
