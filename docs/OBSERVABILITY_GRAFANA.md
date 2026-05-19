# Grafana Import Steps (Prometheus + Dashboard + Alerts)

Prereqs:
- Prometheus is scraping your memory-service metrics endpoint (http://YOUR_HOST:9090/metrics).
- Grafana can reach Prometheus.

Steps:
1) Add Prometheus as a Grafana data source
   - In Grafana: Settings (gear) > Data sources > Add data source > Prometheus
   - URL: http://PROMETHEUS_HOST:PROMETHEUS_PORT (example: http://localhost:9090)
   - Save & Test

2) Import the Memory Service dashboard
   - In Grafana: Dashboards > Import
   - Upload file: dashboards/grafana_memory_service.json
   - Select your Prometheus data source
   - Import

3) Load Prometheus alert rules
   - Copy monitoring/alerts.yml into your Prometheus rules directory
   - Update your Prometheus config to load the rule file:
     rule_files:
       - "alerts.yml"
   - Restart Prometheus
   - Verify alerts are loaded at: http://PROMETHEUS_HOST:9090/rules

4) Validate metrics appear
   - Open the Memory Service dashboard
   - Verify panels show data when the service is under load

5) Optional: Run a quick load test
   - BASE_URL=http://YOUR_HOST:8000 API_TOKEN=YOUR_API_KEY k6 run scripts/load/k6_memory.js
   - Watch Grafana panels update live