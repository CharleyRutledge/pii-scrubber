"""A curated list of common technology/business jargon that spaCy's small
English NER model frequently misclassifies as PERSON/ORGANIZATION/LOCATION -
found by running the tool against real technical resumes/CVs, where dense
lists of tool and framework names (capitalized, proper-noun-shaped) get
mistaken for names and employers, badly over-redacting the document.

This is a narrow, exact-match (case-insensitive) exclusion: an NER match is
only dropped if its full matched text, after stripping surrounding markdown
punctuation, equals one of these terms exactly. It does not affect regex
rules (email, phone, etc.) or NER matches for anything not on this list -
a real person literally named "Grunt" is effectively impossible, so the
false-negative risk this introduces is negligible next to the false-positive
problem it fixes.
"""

NON_PII_TERMS: frozenset[str] = frozenset(
    term.lower()
    for term in [
        # Languages / markup / data formats
        "HTML", "HTML5", "CSS", "CSS3", "SCSS", "Sass", "XML", "JSON", "YAML",
        "SQL", "NoSQL", "GraphQL", "JavaScript", "Javascript", "TypeScript",
        "PHP", "SOAP", "REST", "REST API", "RESTful API", "API", "gRPC",
        # Frontend frameworks/tools
        "React", "Vue", "Angular", "AngularJS", "jQuery", "jQuery UI",
        "Redux", "Babel", "Webpack", "Gulp", "Grunt", "Pug", "Jade",
        "Backbone", "Backbone.js", "Ember", "Ember.js", "Aurelia",
        "Stencil.js",
        # Backend/runtime
        "Node.js", "Express.js", "NPM", "Django", "Flask", "Rails", "ASP.NET",
        "ASP.NET MVC", ".NET",
        # Databases
        "MongoDB", "MySQL", "PostgreSQL", "MariaDB", "Neo4j", "Oracle",
        "MS SQL Server", "SQL Server", "Redis", "DynamoDB", "ORM",
        # DevOps / infra
        "Docker", "Kubernetes", "Git", "GitHub", "GitLab", "Jenkins",
        "Ansible", "Terraform", "AWS", "Azure", "Azure Data Factory", "GCP",
        "CI/CD", "DevOps", "SaaS", "PaaS", "IaaS",
        # Testing / monitoring
        "Cucumber", "Jasmine", "Karma", "Protractor", "BDD", "TDD", "DDD",
        "MSTest", "MStest", "Nagios", "Raygun",
        # Methodology / process
        "Agile", "Scrum", "Kanban", "SDLC", "SOLID", "MVP", "TTM", "ETL",
        "Jira", "Confluence", "Basecamp", "12 Factor App",
        # Enterprise/misc platforms
        "JBoss", "Yii", "GoLand", "SSAS", "SSRS", "POSTGIS", "PostGIS",
        # Misc resume boilerplate
        "KEY SKILLS", "SEO", "UI/UX", "UX", "CEO", "CTO", "CI", "CD",
    ]
)


def is_known_nonpii_term(text: str) -> bool:
    cleaned = text.strip().strip("*").strip("#").strip(":").strip()
    return cleaned.lower() in NON_PII_TERMS
