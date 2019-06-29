
var xMax = 600;
var yMax = 800;
var xStandoff = 20;
var yStandoff = 10;
var divBorders = 20;

function positionTooltip(caller, toolTip)
{


	var mousex = caller.pageX + xStandoff; //Get X coordinates
	var mousey = caller.pageY + yStandoff; //Get Y coordinates

	var posX = 0
	var posY = 0

	var divX = xMax+30;
	var divY = yMax+30;

	var windowYBottom = $(window).height()+$(window).scrollTop();

	if (divX+mousex < $(window).width())
		posX = mousex;
	else
		posX = $(window).width()-(divX+xStandoff);


	if (divY+mousey < windowYBottom)
		posY = mousey;
	else
		posY = windowYBottom-(divY+yStandoff);

	console.log();
	toolTip.css({ top: posY, left: posX })
}

function singleImagePopup()
{
	// Tooltip only Text
	var ttItem = $('.showTT');
	ttItem.hover(function(){
		// Hover over code
		var imageID = $(this).attr('imageID');
		$(this).data('tipText', imageID).removeAttr('imageID');
		$('<div class="tooltip"></div>')
		.html("<img style='max-width:"+xMax+"px; max-height:"+yMax+"px;' src='/images/byid/"+imageID+"'>")
		.appendTo('body')
		.fadeIn('fast');
	}, function() {
		// Hover out code
		$(this).attr('imageID', $(this).data('tipText'));
		$('.tooltip').remove();

	});

	ttItem.mousemove(function(e)
	{
		var tt = $('.tooltip');
		positionTooltip(e, tt);
	});
}


function multiImagePopup()
{
	$.ttStatus = new Object();
	// Tooltip only Text
	var tmp = $('.showTT');
	tmp.hover(
		function(){
			// Hover over code
			var artistID = $(this).attr('artistID');
			$(this).data('tipText', artistID)
			$.ttStatus.indiceNo = 0;
			tmp = $("<p class='tooltip'></p>");
			tmp.html("<img class='tooltip-image' style='max-width:600px;max-height:700px;' src='/images/byoffset/"+artistID+"/"+$.ttStatus.indiceNo+"'>");
			tmp.appendTo('body');
			tmp.fadeIn('fast');
		},
		function()
		{
			// Hover out code
			$(this).attr('artistID', $(this).data('tipText'));
			$('.tooltip').remove();

		});
	tmp.mousemove(
		function(e)
		{
			var artistID = $(this).attr('artistID');
			var mousex = e.pageX + 20; //Get X coordinates
			var mousey = e.pageY + 10; //Get Y coordinates
			var tt = $('.tooltip')


			positionTooltip(e, tt);

			mousex = ~~(mousex / 30);
			if ($.ttStatus.url != mousex)
			{
				$.ttStatus.url = mousex;
				$(".tooltip-image").attr('src', "/images/byoffset/"+artistID+"/"+mousex )
			}
		});
}