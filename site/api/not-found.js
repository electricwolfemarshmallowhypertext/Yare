module.exports = function handler(req, res) {
  res.statusCode = 404;
  res.setHeader("content-type", "application/json; charset=utf-8");
  res.setHeader("cache-control", "no-store");
  res.end(JSON.stringify({ error: "not found" }));
};
