$(document).ready(function() {

    function divide(num, den) {
        if (den == 0) {
            return '-';
        } else {
            return ((num / den * 100).toFixed(2) + ' %');
        }
    }

    function addCommas(nStr) {
        nStr += '';
        x = nStr.split('.');
        x1 = x[0];
        x2 = x.length > 1 ? '.' + x[1] : '';
        var rgx = /(\d+)(\d{3})/;
        while (rgx.test(x1)) {
            x1 = x1.replace(rgx, '$1' + ',' + '$2');
        }
        return x1 + x2;
    }

    $('.js-table').each(function(i, cell) {
        $(this).find('.table').DataTable({
            paging: false,
            searching: false,
            "info": false,
            "order": [
                [0, "desc"]
            ]
        });
    });
    // $('.dataTables_wrapper').find('label').each(function() {
    //     $(this).parent().append($(this).children());
    // });
    // $('.dataTables_filter').find('input').each(function() {
    //     $('input').attr("placeholder", "Search");
    //     $('input').removeClass('form-control-sm');
    // });
    // $('.dataTables_length').addClass('d-flex flex-row');
    // $('.dataTables_filter').addClass('md-form');
    // $('select').addClass('mdb-select');
    // // $('.mdb-select').material_select();
    // $('.mdb-select').removeClass('form-control form-control-sm');
    // $('.dataTables_filter').find('label').remove();


    // Actions if botton 'CURR' is clicked
    $('#btn-curr').on('click', function() {
        if (!$(this).hasClass("btn-active")) {
            // Update botton colors
            $(this).removeClass('btn-normal').addClass('btn-active')
            $('#btn-btc').removeClass('btn-active').addClass('btn-normal')
            // Select columns to display
            $('th[data-curr=curr]').each(function(i, cell) {
                $(this).removeClass('hidden-col');
            });
            $('td[data-curr=curr]').each(function(i, cell) {
                $(this).removeClass('hidden-col');
            });
            $('th[data-curr=btc]').each(function(i, cell) {
                $(this).addClass('hidden-col');
            });
            $('td[data-curr=btc]').each(function(i, cell) {
                $(this).addClass('hidden-col');
            });
        }
    });

    // Actions if botton 'BTC' is clicked
    $('#btn-btc').on('click', function() {
        if (!$(this).hasClass("btn-active")) {
            // Update botton colors
            $(this).removeClass('btn-normal').addClass('btn-active')
            $('#btn-curr').removeClass('btn-active').addClass('btn-normal')
            // Select columns to display
            $('th[data-curr=btc]').each(function(i, cell) {
                $(this).removeClass('hidden-col');
            });
            $('td[data-curr=btc]').each(function(i, cell) {
                $(this).removeClass('hidden-col');
            });
            $('th[data-curr=curr]').each(function(i, cell) {
                $(this).addClass('hidden-col');
            });
            $('td[data-curr=curr]').each(function(i, cell) {
                $(this).addClass('hidden-col');
            });
        }
    });





    // Actions if a 'period button is clicked'
    $('#period-btns .btn').on('click', function() {
        if (!$(this).hasClass("btn-active")) {
            // Update botton colors
            var $period = parseInt($(this).attr("data-period"));
            // Update botton colors
            $('#period-btns .btn').each(function(i, cell) {
                $(this).removeClass('btn-active');
                $(this).addClass('btn-normal');
            });
            $(this).addClass('btn-active');
            $(this).removeClass('btn-normal');

            // Loop table to show selected contents (XS table)
            $('.js-table').each(function(i, cell) {
                var prevPortf = -1;
                var prevPnL = -1;
                var prevPortfBTC = -1;
                var prevPnLBTC = -1;
                var $prevRow = undefined;
                var nextDate = new Date();
                $(this).find('tbody tr').each(function(i, cell) {
                    // Show row in case it was hidden
                    $(this).removeClass('hidden-row');
                    // Check if date is <= nextDate
                    $date = $(this).find('[headers=row-date]').html();
                    var date = new Date($date);
                    if (date.getTime() <= nextDate.getTime()) {
                        // Get values to perform calculations
                        var $example = $(this).find('[headers=row-portf]').html();
                        var lastChars = $example.substring($example.length - 2, $example.length)
                        var $portf = parseFloat($(this).find('[headers=row-portf]').html().replace(/,/g, ''));
                        try {
                            var $pnL = parseFloat($(this).find('[headers=row-pnl]').html().replace(/,/g, ''));
                        } catch (err) {
                            var $pnL = undefined;
                        }
                        var $portfBTC = parseFloat($(this).find('[headers=row-portfBTC]').html());
                        var $pnLBTC = parseFloat($(this).find('[headers=row-pnlBTC]').html());
                        // Check if not first row
                        if ($prevRow != undefined) {
                            // Calculate 'portf-Dif'
                            var calc = addCommas(Math.round(prevPortf - $portf)).toString().concat(lastChars);
                            $prevRow.find('[headers=row-portf-Dif]').html(calc);
                            // Calculate 'portf-DifPerc'
                            calc = divide(prevPortf - $portf, $portf);
                            $prevRow.find('[headers=row-portf-DifPerc]').html(calc);
                            // Calculate 'pnl-Dif'
                            calc = addCommas(Math.round(prevPnL - $pnL)).toString().concat(lastChars);
                            $prevRow.find('[headers=row-pnl-Dif]').html(calc);
                            // Calculate 'pnl-DifPerc'
                            calc = divide(prevPnL - $pnL, $pnL);
                            $prevRow.find('[headers=row-pnl-DifPerc]').html(calc);
                            // Calculate 'portfBTC-Dif'
                            calc = (prevPortfBTC - $portfBTC).toFixed(4).concat(' ฿');
                            $prevRow.find('[headers=row-portfBTC-Dif]').html(calc);
                            // Calculate 'portfBTC-DifPerc'
                            calc = divide(prevPortfBTC - $portfBTC, $portfBTC);
                            $prevRow.find('[headers=row-portfBTC-DifPerc]').html(calc);
                            // Calculate 'pnlBTC-Dif'
                            calc = (prevPnLBTC - $pnLBTC).toFixed(4).concat(' ฿');
                            $prevRow.find('[headers=row-pnlBTC-Dif]').html(calc);
                            // Calculate 'pnlBTC-DifPerc'
                            calc = divide(prevPnLBTC - $pnLBTC, $pnLBTC);
                            $prevRow.find('[headers=row-pnlBTC-DifPerc]').html(calc);
                        }
                        // Calculate next date to be displayed
                        if ($period == 30) {
                            nextDate.setDate(0); // Find last date of prev month
                        } else {
                            nextDate.setDate(date.getDate() - $period);
                        }
                        // Store previous row (to modify Diff columns)
                        $prevRow = $(this)
                        // Store values for next iteration
                        prevPortf = $portf
                        prevPnL = $pnL
                        prevPortfBTC = $portfBTC
                        prevPnLBTC = $pnLBTC
                    } else {
                        $(this).addClass('hidden-row');
                    }
                });
            });
            // Paint colors
            color_table();
        }
    });

    function color_table() {
        // Format table contents (red/green colors)
        $('.color-sign').each(function(i, cell) {
            content = $(this).text();
            if (content.length > 2) {
                num = parseFloat(content.substr(0, content.length - 2));
                if (num < 0) {
                    $(this).css({
                        color: 'red'
                    });
                } else if (num > 0) {
                    $(this).css({
                        color: 'green'
                    });
                } else {
                    $(this).html('-');
                    $(this).css({
                        color: 'black'
                    });
                }

            }
        });
    }

    color_table();



});