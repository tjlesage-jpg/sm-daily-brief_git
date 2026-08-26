---
layout: default
title: South Milwaukee Daily Brief
---

# South Milwaukee Daily Brief

Automated civic updates and recaps for South Milwaukee Common Council and municipal committee meetings.

---

## Recent Meeting Briefings

<ul>
  {% assign raw_briefs = site.pages | where_exp: "item", "item.path contains 'briefings/'" %}
  {% assign sorted_briefs = raw_briefs | sort: "name" | reverse %}
  
  {% for item in sorted_briefs %}
    <li style="margin-bottom: 0.75rem;">
      <a href="{{ item.url | relative_url }}">
        <strong>{{ item.title | default: item.name | remove: ".md" }}</strong>
      </a>
    </li>
  {% endfor %}
</ul>

---

*Powered by automated ingestion and Gemini AI analysis.*
