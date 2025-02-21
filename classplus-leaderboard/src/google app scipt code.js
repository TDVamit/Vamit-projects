 function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('Coupon data')
    .addItem('Update Coupon Data', 'updateCouponData')
    .addToUi();
}

function updateCouponData() {
  var url = ""; // Replace with your endpoint URL
  var options = {
    method: "post",
    muteHttpExceptions: true
  };
  try {
    var response = UrlFetchApp.fetch(url, options);
    Logger.log(response.getContentText());
  } catch (e) {
    Logger.log("Error calling endpoint: " + e.message);
  }
}
