// External JavaScript file for testing
// This script modifies the page to indicate successful execution

(function() {
   // Update the status indicator
   var statusElement = document.getElementById('status');
   if (statusElement) {
      statusElement.textContent = '✓ JavaScript ran successfully';
      statusElement.className = 'status js-success';
   }

   // Update the details paragraph
   var detailsElement = document.getElementById('details');
   if (detailsElement) {
      detailsElement.textContent = 'The external script file (script.js) was loaded and executed successfully. Timestamp: ' + new Date().toISOString();
   }
})();
