$ErrorActionPreference = 'Stop'
$deckRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$deck = Get-Content -LiteralPath (Join-Path $deckRoot 'build/deck.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$scale = 0.6
function Color([string]$hex) {
    $h = $hex.TrimStart('#')
    return [Convert]::ToInt32($h.Substring(0,2),16) + 256*[Convert]::ToInt32($h.Substring(2,2),16) + 65536*[Convert]::ToInt32($h.Substring(4,2),16)
}
function StyleText($shape,$o) {
    $tf=$shape.TextFrame
    $tf.MarginLeft=0; $tf.MarginRight=0; $tf.MarginTop=0; $tf.MarginBottom=0
    $tf.WordWrap=-1; $tf.AutoSize=0
    $r=$tf.TextRange; $r.Text=$o.text; $r.Font.Name=$o.font; $r.Font.Size=[single]($o.size*$scale)
    $r.Font.Color.RGB=(Color $o.color); $r.Font.Bold= $(if($o.bold){-1}else{0})
    $r.ParagraphFormat.SpaceAfter=0; $r.ParagraphFormat.SpaceBefore=0
    if($o.align -eq 'right'){$r.ParagraphFormat.Alignment=3}
}
$app=New-Object -ComObject PowerPoint.Application
$pres=$app.Presentations.Add(0)
try {
    $pres.PageSetup.SlideWidth=960; $pres.PageSetup.SlideHeight=540
    foreach($s in $deck.slides){
        $sl=$pres.Slides.Add($pres.Slides.Count+1,12)
        $sl.FollowMasterBackground=0; $sl.Background.Fill.Solid();$sl.Background.Fill.ForeColor.RGB=(Color $s.bg)
        foreach($o in $s.objects){
            $sh=$null
            switch($o.type){
                'image' {
                    $imagePath=Join-Path (Split-Path -Parent $deckRoot) $o.src
                    $sh=$sl.Shapes.AddPicture($imagePath,0,-1,[single]($o.x*$scale),[single]($o.y*$scale),[single]($o.w*$scale),[single]($o.h*$scale))
                    $sh.AlternativeText=$o.alt
                }
                'text' {
                    $sh=$sl.Shapes.AddTextbox(1,[single]($o.x*$scale),[single]($o.y*$scale),[single]($o.w*$scale),[single]($o.h*$scale))
                    StyleText $sh $o
                    $sh.TextFrame2.AutoSize=0
                    $sh.Left=[single]($o.x*$scale);$sh.Top=[single]($o.y*$scale)
                    $sh.Width=[single]($o.w*$scale);$sh.Height=[single]($o.h*$scale)
                    $sh.AlternativeText=$o.text
                }
                {$_ -in 'rect','ellipse'} {
                    $kind=if($o.type -eq 'ellipse'){9}else{1}
                    $sh=$sl.Shapes.AddShape($kind,[single]($o.x*$scale),[single]($o.y*$scale),[single]($o.w*$scale),[single]($o.h*$scale))
                    if($o.fill){$sh.Fill.Solid();$sh.Fill.ForeColor.RGB=(Color $o.fill)}else{$sh.Fill.Visible=0}
                    if($o.stroke){$sh.Line.ForeColor.RGB=(Color $o.stroke);$sh.Line.Weight=[single]($o.sw*$scale)}else{$sh.Line.Visible=0}
                }
                'line' {
                    $sh=$sl.Shapes.AddLine([single]($o.x*$scale),[single]($o.y*$scale),[single]($o.x2*$scale),[single]($o.y2*$scale))
                    $sh.Line.ForeColor.RGB=(Color $o.color);$sh.Line.Weight=[single]($o.sw*$scale)
                    if($o.dash){$sh.Line.DashStyle=4}
                }
                'path' {
                    # One native freeform, fully editable, with round joined geometry.
                    $pts=$o.points
                    $fb=$sl.Shapes.BuildFreeform(0,[single]($pts[0][0]*$scale),[single]($pts[0][1]*$scale))
                    for($j=1;$j -lt $pts.Count;$j++){$fb.AddNodes(0,0,[single]($pts[$j][0]*$scale),[single]($pts[$j][1]*$scale))}
                    $sh=$fb.ConvertToShape();$sh.Fill.Visible=0;$sh.Line.ForeColor.RGB=(Color $o.color);$sh.Line.Weight=[single]($o.sw*$scale)
                    if($o.dash){$sh.Line.DashStyle=4}
                    $sh.AlternativeText='Synthetic illustrative geometry, not a measured trajectory'
                }
                'table' {
                    $sh=$sl.Shapes.AddTable($o.rows.Count,$o.widths.Count,[single]($o.x*$scale),[single]($o.y*$scale),[single]($o.w*$scale),[single]($o.h*$scale))
                    $tb=$sh.Table
                    for($c=1;$c -le $o.widths.Count;$c++){$tb.Columns.Item($c).Width=[single]($o.w*$o.widths[$c-1]*$scale)}
                    for($r=1;$r -le $o.rows.Count;$r++){
                        $tb.Rows.Item($r).Height=[single]($o.rowh*$scale)
                        for($c=1;$c -le $o.widths.Count;$c++){
                            $cell=$tb.Cell($r,$c).Shape
                            $cell.Fill.Solid();$cell.Fill.ForeColor.RGB=(Color $(if($r -eq 1){'#102C3A'}elseif($r%2 -eq 0){'#FFFFFF'}else{'#E7EFEE'}))
                            $tf=$cell.TextFrame;$tf.MarginLeft=9.6;$tf.MarginRight=7.2;$tf.MarginTop=5;$tf.MarginBottom=3;$tf.VerticalAnchor=3
                            $tr=$tf.TextRange;$tr.Text=$o.rows[$r-1][$c-1];$tr.Font.Name='Segoe UI';$tr.Font.Size=$(if($o.rows.Count -gt 6){13.2}else{13.8});$tr.Font.Bold=$(if($r -eq 1){-1}else{0});$tr.Font.Color.RGB=(Color $(if($r -eq 1){'#FFFFFF'}else{'#102C3A'}));$tr.ParagraphFormat.SpaceAfter=0
                            for($b=1;$b -le 4;$b++){$tb.Cell($r,$c).Borders.Item($b).ForeColor.RGB=(Color '#F1F5F4')}
                        }
                    }
                    $sh.AlternativeText='Editable evidence or pilot acceptance table'
                }
            }
        }
        $sl.NotesPage.Shapes.Placeholders.Item(2).TextFrame.TextRange.Text=$s.notes
    }
    $pptx=Join-Path $deckRoot 'trackguard-pitch.pptx'
    $pdf=Join-Path $deckRoot 'trackguard-pitch.pdf'
    $pres.SaveAs($pptx,24)
    $pres.SaveAs($pdf,32)
    for($i=1;$i -le $pres.Slides.Count;$i++){$pres.Slides.Item($i).Export((Join-Path $deckRoot "qa/slide-$i.png"),'PNG',1600,900)}
    # Native PowerPoint overflow audit. Bounds come from the actual rendering engine.
    $audit=@()
    foreach($sl in $pres.Slides){foreach($sh in $sl.Shapes){if($sh.HasTextFrame -eq -1 -and $sh.TextFrame.HasText -eq -1){
        $tf=$sh.TextFrame
        if($tf.TextRange.BoundHeight -gt ($sh.Height-$tf.MarginTop-$tf.MarginBottom+3)){$audit+=@{slide=$sl.SlideIndex;text=$tf.TextRange.Text;boundHeight=$tf.TextRange.BoundHeight;height=$sh.Height}}
    }}}
    ConvertTo-Json -InputObject @($audit) -Depth 5 | Set-Content -LiteralPath (Join-Path $deckRoot 'qa/text-overflow.json') -Encoding UTF8
    Write-Output "EXPORTED: 6 editable slides, PPTX, PDF, 6 PNG renders. Text overflow flags: $($audit.Count)"
} finally {
    $pres.Close()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($pres)|Out-Null
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app)|Out-Null
}
