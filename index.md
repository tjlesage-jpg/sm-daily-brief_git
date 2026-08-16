---
layout: default
title: South Milwaukee Daily Brief
---

# South Milwaukee Daily Brief

Automated civic updates and recaps for South Milwaukee Common Council and municipal committee meetings.

---

## Recent Meeting Briefings

<ul>
  {% assign briefs = site.pages | where_exp: "item", "item.path contains 'briefings/'" %}
  {% if briefs.size > 0 %}
    {% for item in briefs reversed %}
      <li>
        <a href="{{ item.url | relative_url }}">
          <strong>{{ item.title | default: item.name | remove: ".md" }}</strong>
        </a>
      </li>
    {% endfor %}
  {% else %}
    {% for item in site.briefings reversed %}
      <li>
        <a href="{{ item.url | relative_url }}">
          <strong>{{ item.title | default: item.name | remove: ".md" }}</strong>
        </a>
      </li>
    {% endfor %}
  {% endif %}
</ul>

---

*Powered by automated ingestion and Gemini AI analysis.*
