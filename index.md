---
layout: default
title: South Milwaukee Daily Brief
---

<style>
  html, body {
    background-color: #fdf0f4 !important;
    color: #2b2b2b;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    margin: 0;
    padding: 0;
  }

  .site-wrapper {
    max-width: 1100px;
    margin: 0 auto;
    padding: 24px 20px;
  }

  .site-header {
    text-align: center;
    padding-bottom: 24px;
    border-bottom: 2px solid #f3d1dc;
    margin-bottom: 30px;
  }

  .city-logo {
    max-width: 260px;
    height: auto;
    margin-bottom: 12px;
  }

  .site-header h1 {
    margin: 0;
    font-size: 1.9rem;
    color: #1a1a1a;
  }

  .site-header p {
    margin: 6px 0 0 0;
    color: #555;
    font-size: 1rem;
  }

  .main-layout {
    display: flex;
    flex-direction: row;
    gap: 32px;
    align-items: flex-start;
  }

  /* Left Main Content Feed */
  .content-main {
    flex: 1 1 68%;
  }

  .feed-header {
    margin-top: 0;
    margin-bottom: 20px;
    font-size: 1.4rem;
    color: #1a1a1a;
    border-bottom: 2px solid #f7d6e0;
    padding-bottom: 8px;
  }

  /* Daily Brief Cards */
  .brief-card {
    background: #ffffff;
    padding: 22px;
    border-radius: 8px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    border: 1px solid #f7d6e0;
    margin-bottom: 20px;
  }

  .brief-meta {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
  }

  .badge {
    display: inline-block;
    padding: 3px 8px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    border-radius: 4px;
    letter-spacing: 0.5px;
  }

  .badge-minutes {
    background-color: #d1fae5;
    color: #065f46;
  }

  .badge-agenda {
    background-color: #fef3c7;
    color: #92400e;
  }

  .brief-date {
    font-size: 0.85rem;
    color: #666;
    font-weight: 500;
  }

  .brief-card h3 {
    margin: 0 0 10px 0;
    font-size: 1.15rem;
  }

  .brief-card h3 a {
    color: #991b3b;
    text-decoration: none;
  }

  .brief-card h3 a:hover {
    text-decoration: underline;
  }

  .brief-summary {
    font-size: 0.95rem;
    line-height: 1.5;
    color: #444;
    margin-bottom: 14px;
  }

  .read-more {
    font-size: 0.85rem;
    font-weight: 600;
    color: #991b3b;
    text-decoration: none;
  }

  .read-more:hover {
    text-decoration: underline;
  }

  /* Right Sidebar Area */
  .sidebar-right {
    flex: 0 0 280px;
    background: #ffffff;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    border: 1px solid #f7d6e0;
  }

  .sidebar-right h3 {
    margin-top: 0;
    margin-bottom: 14px;
    font-size: 1rem;
    color: #333;
    border-bottom: 1px solid #f0ccd7;
    padding-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .briefing-list {
    list-style-type: none;
    padding-left: 0;
    margin: 0;
  }

  .briefing-list li {
    margin-bottom: 10px;
    line-height: 1.35;
  }

  .briefing-list a {
    font-size: 0.82rem;
    color: #991b3b;
    text-decoration: none;
    display: block;
    word-break: break-word;
  }

  .briefing-list a:hover {
    text-decoration: underline;
    color: #670d24;
  }

  @media (max-width: 768px) {
    .main-layout {
      flex-direction: column;
    }
    .sidebar-right {
      width: 100%;
    }
  }
</style>

<div class="site-wrapper">

  <header class="site-header">
    <img 
      src="https://play-lh.googleusercontent.com/3Ki9iG_kkCa8uzhznbIQddTB9EwLtW1VIbEMYmdX_v37e_ezRwc-9oCT5UVyMnQGRTKC0HmzP8oCSFA34Nv6gfI=w600-h300-pc0xffffff-pd" 
      alt="City of South Milwaukee Logo" 
      class="city-logo"
    />
    <h1>South Milwaukee Daily Brief</h1>
    <p>Automated civic recaps and meeting intelligence for local residents.</p>
  </header>

  <div class="main-layout">
    
    <!-- Left Column: Daily Briefing Feed with Executive Summaries -->
    <main class="content-main">
      <h2 class="feed-header">Latest Meeting Briefs</h2>
      
      {% assign raw_briefs = site.pages | where_exp: "item", "item.path contains 'briefings/'" %}
      {% assign sorted_briefs = raw_briefs | sort: "name" | reverse %}

      {% for item in sorted_briefs %}
        <article class="brief-card">
          <div class="brief-meta">
            {% if item.doc_type == "Minutes" or item.name contains "Minutes" %}
              <span class="badge badge-minutes">Approved Minutes</span>
            {% else %}
              <span class="badge badge-agenda">Meeting Agenda</span>
            {% endif %}
            <span class="brief-date">{{ item.date | default: item.name | slice: 0, 10 }}</span>
          </div>
          
          <h3>
            <a href="{{ item.url | relative_url }}">
              {{ item.title | default: item.name | remove: ".md" }}
            </a>
          </h3>

          <div class="brief-summary">
            {% if item.summary %}
              {{ item.summary }}
            {% else %}
              {{ item.content | strip_html | truncatewords: 35 }}
            {% endif %}
          </div>

          <a href="{{ item.url | relative_url }}" class="read-more">Read Full Meeting Brief &rarr;</a>
        </article>
      {% endfor %}
    </main>

    <!-- Right Sidebar: Quick Navigation Index -->
    <aside class="sidebar-right">
      <h3>Meeting Archive</h3>
      <ul class="briefing-list">
        {% for item in sorted_briefs %}
          <li>
            <a href="{{ item.url | relative_url }}">
              {{ item.title | default: item.name | remove: ".md" }}
            </a>
          </li>
        {% endfor %}
      </ul>
    </aside>

  </div>

</div>
