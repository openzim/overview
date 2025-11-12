// External JavaScript file that uses eval() for testing
// This tests whether eval() is allowed in the ZIM reader

(function() {
   try {
      // Code to be evaluated
      var codeToEval = `
         var statusElement = document.getElementById('status');
         if (statusElement) {
            statusElement.textContent = '✓ JavaScript with eval() ran successfully';
            statusElement.className = 'status js-success';
         }

         var detailsElement = document.getElementById('details');
         if (detailsElement) {
            detailsElement.textContent = 'The eval() function executed successfully in the external script file. This indicates that eval() is not blocked by CSP. Timestamp: ' + new Date().toISOString();
         }
      `;

      // Execute the code using eval()
      eval(codeToEval);
   } catch (error) {
      // If eval() fails (e.g., blocked by CSP), show error
      var statusElement = document.getElementById('status');
      if (statusElement) {
         statusElement.textContent = '⚠ eval() was blocked or failed';
         statusElement.className = 'status';
         statusElement.style.backgroundColor = '#e67e22';
         statusElement.style.color = 'white';
      }

      var detailsElement = document.getElementById('details');
      if (detailsElement) {
         detailsElement.textContent = 'Error: ' + error.message + '. This may be due to Content Security Policy (CSP) restrictions.';
      }
   }
})();
