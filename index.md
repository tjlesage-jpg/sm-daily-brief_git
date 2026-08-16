---
layout: default
title: South Milwaukee Daily Brief
---

# South Milwaukee Daily Brief

Automated civic updates and recaps for South Milwaukee Common Council and municipal committee meetings.

---

## Recent Meeting Briefings

<ul>
  {% for item in site.briefings reversed %}
    <li>
      <a href="{{ item.url | relative_url }}"><strong>{{ item.title | default: item.slug }}</strong></a>
    </li>
  {% endfor %}
</ul>

---

*Powered by automated ingestion and Gemini AI analysis.*
