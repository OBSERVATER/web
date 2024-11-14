$(document).ready(function () {
        $('#f').on('submit', function (event) {
            event.preventDefault();
            const x = $('#account').val();
            const y = $('#password').val();
            alert("A")
            $.ajax({
                 url: '/run-script',
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify({ account: x, password: y, operation: operation }),
                    success: function(response) {
                        $('#output').text(response.output);
                    },
                error: function (error) {
                    $('#output').text('Error: ' + error.responseText);
                }
            });
        });
    });