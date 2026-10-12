module.exports = function handler(req, res) {
  res.statusCode = 410;
  res.setHeader("content-type", "application/json; charset=utf-8");
  res.setHeader("cache-control", "no-store");
  res.end(JSON.stringify({ error: "legacy endpoint retired", endpoint: "/api/verified-handoff" }));
};
