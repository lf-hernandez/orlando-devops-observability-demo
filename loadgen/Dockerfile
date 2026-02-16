FROM grafana/k6:0.54.0

COPY script.js /script.js

ENTRYPOINT ["k6", "run", "/script.js"]
