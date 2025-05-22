module.exports = {
  logResponse: function (req, res, context, ee, next) {
    console.log("📥 Response status:", res.statusCode);
    console.log("📦 Response body:", res.body);
    if (res.statusCode >= 400 || !res.body) {
      console.error("❌ Failed request or empty body");
      console.error("Headers:", res.headers);
    }
    return next();
  }
};
