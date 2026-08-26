---
layout: default
title: South Milwaukee Daily Brief
---

<style>
  /* Base page background */
  html, body {
    background-color: #fdf0f4 !important; /* Very light subtle pink */
    color: #2b2b2b;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    margin: 0;
    padding: 0;
  }

  /* Container wrapper */
  .site-wrapper {
    max-width: 1100px;
    margin: 0 auto;
    padding: 24px 20px;
  }

  /* Header and City Logo */
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

  /* Two-column layout grid */
  .main-layout {
    display: flex;
    flex-direction: row;
    gap: 36px;
    align-items: flex-start;
  }

  /* Left Main Content Area */
  .content-main {
    flex: 1 1 65%;
    background: #ffffff;
    padding: 28px;
    border-radius: 8px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    border: 1px solid #f7d6e0;
  }

  /* Right Sidebar Area */
  .sidebar-right {
    flex: 0 0 300px;
    background: #ffffff;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    border: 1px solid #f7d6e0;
  }

  .sidebar-right h3 {
    margin-top: 0;
    margin-bottom: 14px;
    font-size: 1.05rem;
    color: #333;
    border-bottom: 1px solid #f0ccd7;
    padding-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  /* Smaller-font archive links list */
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
    font-size: 0.85rem; /* Smaller font */
    color: #991b3b;     /* Deep accent red/crimson */
    text-decoration: none;
    display: block;
    word-break: break-word;
  }

  .briefing-list a:hover {
    text-decoration: underline;
    color: #670d24;
  }

  /* Responsive behavior for mobile devices */
  @media (max-width: 768px) {
    .main-layout {
      flex-direction: column;
    }
    .sidebar-right {
      width: 100%;
      flex: auto;
    }
  }
</style>

<div class="site-wrapper">

  <!-- Header with City Logo -->
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
    
    <!-- Main Content Area -->
    <main class="content-main">
      <h2>Civic Intelligence & Overview</h2>
      <p>
        Welcome to the <strong>South Milwaukee Daily Brief</strong>. This platform automatically monitors the City of South Milwaukee's AgendaCenter, extracts official meeting packets, and publishes clear, structured summaries of Common Council decisions, infrastructure initiatives, roll-call votes, and public hearings.
      </p>
      <p>
        Select any past meeting or agenda preview from the <strong>Meeting Archive</strong> on the right to read the complete breakdown.
      </p>
      <hr style="border: 0; border-top: 1px solid #f7d6e0; margin: 24px 0;" />
      <small style="color: #777;">
        Updated automatically via GitHub Actions and Google GenAI.
      </small>
    </main>

    <!-- Right Sidebar with smaller-font meeting links -->
    <aside class="sidebar-right">
      <h3>Meeting Archive</h3>
      <ul class="briefing-list">
        {% assign raw_briefs = site.pages | where_exp: "item", "item.path contains 'briefings/'" %}
        {% assign sorted_briefs = raw_briefs | sort: "name" | reverse %}
        
        {% if sorted_briefs.size > 0 %}
          {% for item in sorted_briefs %}
            <li>
              <a href="{{ item.url | relative_url }}">
                {{ item.title | default: item.name | remove: ".md" }}
              </a>
            </li>
          {% endfor %}
        {% else %}
          {% for item in site.briefings reversed %}
            <li>
              <a href="{{ item.url | relative_url }}">
                {{ item.title | default: item.name | remove: ".md" }}
              </a>
            </li>
          {% endfor %}
        {% endif %}
      </ul>
    </aside>

  </div>

</div>
