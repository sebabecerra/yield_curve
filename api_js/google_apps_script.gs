function doPost(e) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("access_log") || SpreadsheetApp.getActiveSpreadsheet().insertSheet("access_log");

  if (sheet.getLastRow() === 0) {
    sheet.appendRow(["timestamp", "email", "language", "page", "user_agent"]);
  }

  const payload = e && e.postData && e.postData.contents
    ? JSON.parse(e.postData.contents)
    : {};

  sheet.appendRow([
    new Date(),
    payload.email || "",
    payload.language || "",
    payload.page || "",
    payload.userAgent || "",
  ]);

  return ContentService
    .createTextOutput(JSON.stringify({ ok: true }))
    .setMimeType(ContentService.MimeType.JSON);
}
