param([switch]$StartHidden)

Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$ErrorActionPreference = 'Stop'
$script:AutomationDir = Split-Path -Parent $PSScriptRoot
$script:ProjectDir = $script:AutomationDir
$initializer = Join-Path $PSScriptRoot '初始化配置.ps1'
if (-not (Test-Path -LiteralPath (Join-Path $script:ProjectDir '.env')) -and (Test-Path -LiteralPath $initializer)) { & $initializer -ProjectDir $script:ProjectDir }
$script:Python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $script:Python) { $script:Python = (Get-Command py.exe -ErrorAction SilentlyContinue).Source }
$script:Src = Join-Path $script:AutomationDir 'src'
$script:ExitRequested = $false
$script:LastNotice = ''

function Invoke-MonitorCli([string[]]$Arguments) {
    $old = $env:PYTHONPATH
    $oldUtf8 = $env:PYTHONUTF8
    $oldIoEncoding = $env:PYTHONIOENCODING
    try {
        $env:PYTHONPATH = if ($old) { "$script:Src;$old" } else { $script:Src }
        $env:PYTHONUTF8 = '1'
        $env:PYTHONIOENCODING = 'utf-8'
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $script:Python
        $psi.Arguments = '-m rpa_monitor.cli ' + (($Arguments | ForEach-Object { '"' + ($_ -replace '"','\"') + '"' }) -join ' ')
        $psi.WorkingDirectory = $script:ProjectDir
        $psi.UseShellExecute = $false; $psi.CreateNoWindow = $true; $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
        $psi.StandardOutputEncoding = [Text.Encoding]::UTF8; $psi.StandardErrorEncoding = [Text.Encoding]::UTF8
        $p = [Diagnostics.Process]::Start($psi); $out = $p.StandardOutput.ReadToEnd(); $err = $p.StandardError.ReadToEnd(); $p.WaitForExit()
        if (-not $out.Trim()) { throw "后台程序没有返回数据。$err" }
        $last = ($out.Trim() -split "`r?`n")[-1] | ConvertFrom-Json
        if ($p.ExitCode -ne 0 -or ($last.PSObject.Properties.Name -contains 'ok' -and $last.ok -eq $false)) { if ($last.error) { throw $last.error } else { throw $err } }
        return $last
    } finally {
        $env:PYTHONPATH = $old
        $env:PYTHONUTF8 = $oldUtf8
        $env:PYTHONIOENCODING = $oldIoEncoding
    }
}

[xml]$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
 Title="RPA 异常闭环控制台" Width="1380" Height="850" MinWidth="1100" MinHeight="700" WindowStartupLocation="CenterScreen" Background="#F3F5F8">
 <Window.Resources>
  <Style TargetType="Button"><Setter Property="Margin" Value="4"/><Setter Property="Padding" Value="12,7"/><Setter Property="Background" Value="#FFFFFF"/><Setter Property="BorderBrush" Value="#D5DAE3"/></Style>
  <Style TargetType="TextBox"><Setter Property="Margin" Value="4"/><Setter Property="Padding" Value="6"/></Style>
  <Style TargetType="ComboBox"><Setter Property="Margin" Value="4"/><Setter Property="Padding" Value="5"/></Style>
  <Style TargetType="CheckBox"><Setter Property="Margin" Value="8,4"/></Style>
 </Window.Resources>
 <DockPanel Margin="14">
  <Border DockPanel.Dock="Top" Background="#17233C" CornerRadius="10" Padding="18" Margin="0,0,0,10">
   <Grid><Grid.ColumnDefinitions><ColumnDefinition/><ColumnDefinition Width="Auto"/></Grid.ColumnDefinitions>
    <StackPanel><TextBlock Text="RPA 异常闭环控制台" Foreground="White" FontSize="25" FontWeight="SemiBold"/><TextBlock Name="StatusText" Text="正在读取运行状态…" Foreground="#C9D5EF" Margin="0,6,0,0"/></StackPanel>
    <StackPanel Grid.Column="1" Orientation="Horizontal" VerticalAlignment="Center"><TextBlock Text="下次触发：" Foreground="#C9D5EF" VerticalAlignment="Center"/><TextBlock Name="NextRunText" Text="--" Foreground="#6FE5A8" FontSize="17" FontWeight="Bold" VerticalAlignment="Center"/><Button Name="PauseButton" Content="暂停巡检" Margin="18,0,0,0"/></StackPanel>
   </Grid>
  </Border>
  <TabControl Name="MainTabs">
   <TabItem Header="运行与异常">
    <Grid Margin="8"><Grid.RowDefinitions><RowDefinition Height="Auto"/><RowDefinition/><RowDefinition Height="180"/></Grid.RowDefinitions>
     <WrapPanel Margin="0,0,0,8">
      <Button Name="AttentionButton" Content="需关注异常" Background="#FFE7E5"/><Button Name="ErrorsButton" Content="全部异常"/><Button Name="AllButton" Content="全部运行记录"/>
      <ComboBox Name="StatusFilter" Width="125"><ComboBoxItem Content="全部状态" IsSelected="True"/><ComboBoxItem Content="运行中"/><ComboBoxItem Content="等待调度"/><ComboBoxItem Content="完成"/><ComboBoxItem Content="停止中"/><ComboBoxItem Content="已停止"/><ComboBoxItem Content="异常"/></ComboBox>
      <TextBox Name="SearchBox" Width="230" ToolTip="搜索任务名、机器人、错误摘要"/><Button Name="RefreshButton" Content="刷新"/><Button Name="ScanButton" Content="立即巡检"/><Button Name="ColumnsButton" Content="选择显示列"/><Button Name="CopyButton" Content="复制任务名"/><Button Name="RecycleButton" Content="打开回收站"/>
     </WrapPanel>
     <DataGrid Name="RecordsGrid" Grid.Row="1" AutoGenerateColumns="False" IsReadOnly="False" SelectionMode="Single" CanUserAddRows="False" HeadersVisibility="Column" GridLinesVisibility="Horizontal" Background="White" AlternatingRowBackground="#F8FAFD">
      <DataGrid.RowStyle><Style TargetType="DataGridRow"><Setter Property="Opacity" Value="1"/><Setter Property="Foreground" Value="#202633"/><Style.Triggers><DataTrigger Binding="{Binding Resolved}" Value="True"><Setter Property="Opacity" Value="0.48"/><Setter Property="Background" Value="#E2E5EA"/><Setter Property="Foreground" Value="#6E7685"/></DataTrigger></Style.Triggers></Style></DataGrid.RowStyle>
      <DataGrid.ContextMenu><ContextMenu><MenuItem Name="TrashMenu" Header="放入回收站"/></ContextMenu></DataGrid.ContextMenu>
      <DataGrid.Columns>
       <DataGridTemplateColumn Header="已解决" Width="70"><DataGridTemplateColumn.CellTemplate><DataTemplate><CheckBox IsChecked="{Binding Resolved}" HorizontalAlignment="Center" Name="SolvedCheck"/></DataTemplate></DataGridTemplateColumn.CellTemplate></DataGridTemplateColumn>
       <DataGridTextColumn Header="触发时间" Binding="{Binding TriggerTime}" Width="155"/>
       <DataGridTextColumn Header="任务名称" Binding="{Binding TaskName}" Width="240"/>
       <DataGridTextColumn Header="任务类型" Binding="{Binding TaskType}" Width="90"/>
       <DataGridTextColumn Header="机器人" Binding="{Binding RobotClientName}" Width="100"/>
       <DataGridTextColumn Header="状态" Binding="{Binding StatusCn}" Width="85"/>
       <DataGridTextColumn Header="连续异常" Binding="{Binding Consecutive}" Width="80"/>
       <DataGridTextColumn Header="AI状态" Binding="{Binding AiState}" Width="115"/>
       <DataGridTextColumn Header="错误摘要" Binding="{Binding Summary}" Width="*"/>
       <DataGridTemplateColumn Header="操作" Width="160"><DataGridTemplateColumn.CellTemplate><DataTemplate><StackPanel Orientation="Horizontal"><Button Content="AI分析" Name="AiRowButton" Padding="7,3"/><Button Content="重试" Name="RetryRowButton" Padding="7,3"/></StackPanel></DataTemplate></DataGridTemplateColumn.CellTemplate></DataGridTemplateColumn>
      </DataGrid.Columns>
     </DataGrid>
     <Grid Grid.Row="2" Margin="0,10,0,0"><Grid.ColumnDefinitions><ColumnDefinition Width="2*"/><ColumnDefinition Width="*"/></Grid.ColumnDefinitions>
      <GroupBox Header="错误详情 / AI 建议" Margin="0,0,8,0"><TextBox Name="DetailText" IsReadOnly="True" TextWrapping="Wrap" VerticalScrollBarVisibility="Auto" BorderThickness="0"/></GroupBox>
      <GroupBox Header="异常截图（点击放大）" Grid.Column="1"><Grid><Image Name="ScreenshotImage" Stretch="Uniform" Cursor="Hand" ToolTip="点击打开大图；在大图中滚动鼠标滚轮可缩放"/><TextBlock Name="NoScreenshotText" Text="本次异常无截图" Foreground="#7B8495" HorizontalAlignment="Center" VerticalAlignment="Center" IsHitTestVisible="False"/></Grid></GroupBox>
     </Grid>
    </Grid>
   </TabItem>
   <TabItem Header="巡检设置">
    <ScrollViewer><StackPanel Margin="22" MaxWidth="880" HorizontalAlignment="Left">
     <TextBlock Text="巡检计划" FontSize="20" FontWeight="SemiBold"/><WrapPanel Margin="0,12,0,4"><TextBlock Text="开始时间" VerticalAlignment="Center"/><TextBox Name="StartTimeBox" Width="80"/><TextBlock Text="结束时间" VerticalAlignment="Center"/><TextBox Name="EndTimeBox" Width="80"/><TextBlock Text="频率（分钟）" VerticalAlignment="Center"/><TextBox Name="FrequencyBox" Width="70"/></WrapPanel>
     <CheckBox Name="RosterCheck" Content="按飞书排班日历判断当天是否执行（每天只读取一次）"/>
     <Separator Margin="0,14"/><TextBlock Text="AI 分析与立即重试" FontSize="20" FontWeight="SemiBold"/>
     <CheckBox Name="AutoRetryCheck" Content="允许 AI 判断后自动立即重试（默认关闭）"/>
     <WrapPanel><TextBlock Text="最大重试次数（1～3）" VerticalAlignment="Center"/><ComboBox Name="MaxRetryBox" Width="70"><ComboBoxItem Content="1"/><ComboBoxItem Content="2"/><ComboBoxItem Content="3"/></ComboBox><TextBlock Text="重试超时（分钟）" VerticalAlignment="Center"/><TextBox Name="RetryTimeoutBox" Width="70"/></WrapPanel>
     <CheckBox Name="RunningGuardCheck" Content="同名任务正在运行时禁止自动重试"/><CheckBox Name="RiskGuardCheck" Content="命中高风险关键词时禁止自动重试"/><CheckBox Name="EvidenceGuardCheck" Content="AI 证据不足时禁止自动重试"/><CheckBox Name="RecentSuccessCheck" Content="近期同名任务无成功记录时禁止自动重试"/>
     <TextBlock Text="自动重试黑名单（每行一个任务名，默认空白）" Margin="4,10,0,0"/><TextBox Name="BlacklistBox" Height="85" AcceptsReturn="True" VerticalScrollBarVisibility="Auto"/>
     <TextBlock Text="高风险关键词（每行一个）" Margin="4,10,0,0"/><TextBox Name="RiskWordsBox" Height="85" AcceptsReturn="True" VerticalScrollBarVisibility="Auto"/>
     <WrapPanel Margin="0,14,0,0"><Button Name="SaveButton" Content="保存设置" Background="#2E6CE6" Foreground="White"/><TextBlock Name="SaveHint" VerticalAlignment="Center" Foreground="#27875D"/></WrapPanel>
     <Border Background="#FFF8E4" CornerRadius="6" Padding="12" Margin="4,14"><TextBlock TextWrapping="Wrap" Text="当前版本仅支持立即重试。排期重试已保留 Gantt/数据库适配、机器空闲窗口、到点复核和冲突顺延框架，但不会读取 PostgreSQL，也不会自动排期。"/></Border>
    </StackPanel></ScrollViewer>
   </TabItem>
  </TabControl>
 </DockPanel>
</Window>
'@
$reader = New-Object System.Xml.XmlNodeReader $xaml
$window = [Windows.Markup.XamlReader]::Load($reader)
foreach ($name in @('StatusText','NextRunText','PauseButton','AttentionButton','ErrorsButton','AllButton','StatusFilter','SearchBox','RefreshButton','ScanButton','ColumnsButton','CopyButton','RecycleButton','RecordsGrid','TrashMenu','DetailText','ScreenshotImage','NoScreenshotText','StartTimeBox','EndTimeBox','FrequencyBox','RosterCheck','AutoRetryCheck','MaxRetryBox','RetryTimeoutBox','RunningGuardCheck','RiskGuardCheck','EvidenceGuardCheck','RecentSuccessCheck','BlacklistBox','RiskWordsBox','SaveButton','SaveHint')) { Set-Variable -Name $name -Value $window.FindName($name) -Scope Script }

$script:View = 'attention'; $script:Rows = @(); $script:Settings = $null; $script:NextDue = $null
function Get-ContentText($v) { if ($null -eq $v) { '' } else { [string]$v } }
function Convert-Row($record, [bool]$wrapped) {
    $job = if ($wrapped) { $record.job } else { $record }
    $analysis = if ($wrapped) { $record.analysis } else { $null }
    $rawTaskName = Get-ContentText $job.taskName
    $robotName = Get-ContentText $job.robotName
    $advanced = if ($job.PSObject.Properties.Name -contains 'isAdvancedTask') { [bool]$job.isAdvancedTask } else { -not $rawTaskName -and [bool]$robotName }
    $displayTaskName = if ($job.displayTaskName) { Get-ContentText $job.displayTaskName } elseif ($rawTaskName) { $rawTaskName } elseif ($robotName) { $robotName } else { '未命名任务' }
    [pscustomobject]@{
        JobUuid=Get-ContentText $job.jobUuid; TriggerTime=Get-ContentText $job.triggerTime; TaskName=$displayTaskName; TaskType=if($advanced){'高级任务'}else{'普通任务'}
        RobotClientName=Get-ContentText $job.robotClientName; StatusCn=Get-ContentText $job.statusCn
        Consecutive=Get-ContentText $job.consecutiveErrorCount; AiState=if ($record.aiState -eq 'failed_waiting') {'AI分析失败/待人工'} elseif ($record.aiState -eq 'done') {'已分析'} elseif ($record.aiState -eq 'skipped_loop') {'循环任务不分析'} else {Get-ContentText $record.aiState}
        Summary=if ($analysis.summary) {Get-ContentText $analysis.summary} elseif ($job.remark) {Get-ContentText $job.remark} else {Get-ContentText $job.message}
        Resolved=[bool]$record.resolved; ScreenshotPath=Get-ContentText $job.screenshotPath; Analysis=$analysis; Raw=$record
    }
}
function Load-Records {
    try {
        $data = Invoke-MonitorCli @('data','--view',$script:View)
        $wrapped = $script:View -ne 'all'; $rows = @($data | ForEach-Object { Convert-Row $_ $wrapped })
        $status = [string](($StatusFilter.SelectedItem).Content); $term = $SearchBox.Text.Trim()
        if ($status -ne '全部状态') { $rows = @($rows | Where-Object StatusCn -eq $status) }
        if ($term) { $rows = @($rows | Where-Object { $_.TaskName -like "*$term*" -or $_.TaskType -like "*$term*" -or $_.RobotClientName -like "*$term*" -or $_.Summary -like "*$term*" }) }
        $script:Rows = $rows; $RecordsGrid.ItemsSource = $rows
        $StatusText.Text = "当前显示 $($rows.Count) 条；窗口关闭后仍在后台巡检"
    } catch { $StatusText.Text = "读取失败：$($_.Exception.Message)" }
}
function Load-Settings {
    $script:Settings = Invoke-MonitorCli @('settings-get')
    $StartTimeBox.Text=$script:Settings.start_time; $EndTimeBox.Text=$script:Settings.end_time; $FrequencyBox.Text=$script:Settings.frequency_minutes
    $RosterCheck.IsChecked=[bool]$script:Settings.read_roster; $AutoRetryCheck.IsChecked=[bool]$script:Settings.ai_auto_retry
    $MaxRetryBox.SelectedIndex=[Math]::Max(0,[Math]::Min(2,[int]$script:Settings.max_auto_retries-1)); $RetryTimeoutBox.Text=$script:Settings.retry_timeout_minutes
    $RunningGuardCheck.IsChecked=[bool]$script:Settings.block_if_same_task_running; $RiskGuardCheck.IsChecked=[bool]$script:Settings.block_high_risk_keywords
    $EvidenceGuardCheck.IsChecked=[bool]$script:Settings.block_if_evidence_insufficient; $RecentSuccessCheck.IsChecked=[bool]$script:Settings.require_recent_success
    $BlacklistBox.Text=($script:Settings.retry_blacklist -join "`r`n"); $RiskWordsBox.Text=($script:Settings.retry_block_keywords -join "`r`n")
    if ($script:Settings.paused) { $PauseButton.Content='继续巡检' } else { $PauseButton.Content='暂停巡检' }
    foreach($col in $RecordsGrid.Columns){if($script:Settings.hidden_columns -contains [string]$col.Header){$col.Visibility='Collapsed'}}
}
function Calculate-NextDue {
    if ($script:Settings.paused) { return '已暂停' }
    $now=Get-Date; $freq=[Math]::Max(1,[int]$script:Settings.frequency_minutes); $start=[datetime]::ParseExact($script:Settings.start_time,'HH:mm',$null); $end=[datetime]::ParseExact($script:Settings.end_time,'HH:mm',$null)
    $startToday=$now.Date.Add($start.TimeOfDay); $endToday=$now.Date.Add($end.TimeOfDay)
    if ($now -lt $startToday) { return $startToday }
    if ($now -gt $endToday) { return $startToday.AddDays(1) }
    $elapsed=($now-$startToday).TotalMinutes; $steps=[Math]::Floor($elapsed/$freq)+1; $next=$startToday.AddMinutes($steps*$freq)
    if ($next -gt $endToday) { $next=$startToday.AddDays(1) }; return $next
}
function Reset-NextDue { $script:NextDue=Calculate-NextDue; $NextRunText.Text=if($script:NextDue -is [datetime]){$script:NextDue.ToString('MM-dd HH:mm')}else{[string]$script:NextDue} }
function Save-CurrentSettings {
    if ($StartTimeBox.Text -notmatch '^([01]\d|2[0-3]):[0-5]\d$' -or $EndTimeBox.Text -notmatch '^([01]\d|2[0-3]):[0-5]\d$') { throw '时间必须使用 HH:mm 格式' }
    $frequency=0; if (-not [int]::TryParse($FrequencyBox.Text,[ref]$frequency) -or $frequency -lt 1) { throw '频率必须是正整数' }
    $timeout=0; if (-not [int]::TryParse($RetryTimeoutBox.Text,[ref]$timeout) -or $timeout -lt 1) { throw '重试超时必须是正整数' }
    $script:Settings.start_time=$StartTimeBox.Text; $script:Settings.end_time=$EndTimeBox.Text; $script:Settings.frequency_minutes=$frequency
    $script:Settings.read_roster=[bool]$RosterCheck.IsChecked; $script:Settings.ai_auto_retry=[bool]$AutoRetryCheck.IsChecked; $script:Settings.max_auto_retries=$MaxRetryBox.SelectedIndex+1; $script:Settings.retry_timeout_minutes=$timeout
    $script:Settings.block_if_same_task_running=[bool]$RunningGuardCheck.IsChecked; $script:Settings.block_high_risk_keywords=[bool]$RiskGuardCheck.IsChecked; $script:Settings.block_if_evidence_insufficient=[bool]$EvidenceGuardCheck.IsChecked; $script:Settings.require_recent_success=[bool]$RecentSuccessCheck.IsChecked
    $script:Settings.retry_blacklist=@($BlacklistBox.Text -split "`r?`n" | Where-Object {$_.Trim()} | ForEach-Object {$_.Trim()}); $script:Settings.retry_block_keywords=@($RiskWordsBox.Text -split "`r?`n" | Where-Object {$_.Trim()} | ForEach-Object {$_.Trim()})
    $json=$script:Settings | ConvertTo-Json -Depth 8 -Compress; $script:Settings=Invoke-MonitorCli @('settings-save',$json); Reset-NextDue
}

$AttentionButton.Add_Click({$script:View='attention';Load-Records}); $ErrorsButton.Add_Click({$script:View='errors';Load-Records}); $AllButton.Add_Click({$script:View='all';Load-Records})
$RefreshButton.Add_Click({Load-Records}); $StatusFilter.Add_SelectionChanged({if($window.IsLoaded){Load-Records}}); $SearchBox.Add_TextChanged({if($window.IsLoaded){Load-Records}})
$ScanButton.Add_Click({ try{$StatusText.Text='正在巡检…';[Windows.Forms.Application]::DoEvents();$r=Invoke-MonitorCli @('scan','--force');$StatusText.Text="巡检完成：读取 $($r.fetched) 条，需关注 $($r.attention) 条";Load-Records}catch{[Windows.MessageBox]::Show($_.Exception.Message,'巡检失败','OK','Error')}})
$SaveButton.Add_Click({try{Save-CurrentSettings;$SaveHint.Text='已保存，新设置立即生效'}catch{[Windows.MessageBox]::Show($_.Exception.Message,'设置错误','OK','Warning')}})
$PauseButton.Add_Click({$script:Settings.paused=-not [bool]$script:Settings.paused;Save-CurrentSettings;$PauseButton.Content=if($script:Settings.paused){'继续巡检'}else{'暂停巡检'}})
$CopyButton.Add_Click({if($RecordsGrid.SelectedItem){[Windows.Clipboard]::SetText($RecordsGrid.SelectedItem.TaskName);$StatusText.Text='任务名称已复制'}})
$RecordsGrid.Add_SelectionChanged({$r=$RecordsGrid.SelectedItem;if(-not $r){return};$DetailText.Text="任务：$($r.TaskName)`r`n任务类型：$($r.TaskType)`r`n机器人：$($r.RobotClientName)`r`n状态：$($r.StatusCn)`r`n错误摘要：$($r.Summary)`r`n`r`nAI分析：`r`n$($r.Analysis | ConvertTo-Json -Depth 8)";$ScreenshotImage.Source=$null;if($r.ScreenshotPath -and (Test-Path -LiteralPath $r.ScreenshotPath)){$img=New-Object Windows.Media.Imaging.BitmapImage;$img.BeginInit();$img.CacheOption='OnLoad';$img.UriSource=New-Object Uri($r.ScreenshotPath);$img.EndInit();$ScreenshotImage.Source=$img;$NoScreenshotText.Visibility='Collapsed'}else{$NoScreenshotText.Visibility='Visible'}})
$ScreenshotImage.Add_MouseLeftButtonUp({
    if (-not $ScreenshotImage.Source) { return }
    $preview = New-Object Windows.Window
    $preview.Title = '异常截图 - 鼠标滚轮缩放'
    $preview.Width = 1100; $preview.Height = 760; $preview.MinWidth = 640; $preview.MinHeight = 420
    $preview.WindowStartupLocation = 'CenterOwner'; $preview.Owner = $window; $preview.Background = '#171A20'
    $scroll = New-Object Windows.Controls.ScrollViewer
    $scroll.HorizontalScrollBarVisibility = 'Auto'; $scroll.VerticalScrollBarVisibility = 'Auto'
    $large = New-Object Windows.Controls.Image; $large.Source = $ScreenshotImage.Source; $large.Stretch = 'None'; $large.Margin = '20'; $large.Cursor = 'Hand'
    $scale = New-Object Windows.Media.ScaleTransform; $scale.ScaleX = 1.25; $scale.ScaleY = 1.25; $large.LayoutTransform = $scale
    $scroll.Content = $large; $preview.Content = $scroll
    $preview.Add_MouseWheel({param($sender,$eventArgs);$step=if($eventArgs.Delta -gt 0){0.15}else{-0.15};$next=[Math]::Max(0.25,[Math]::Min(5.0,$scale.ScaleX+$step));$scale.ScaleX=$next;$scale.ScaleY=$next;$eventArgs.Handled=$true})
    $preview.ShowDialog() | Out-Null
})
$RecordsGrid.AddHandler([Windows.Controls.Button]::ClickEvent,[Windows.RoutedEventHandler]{param($s,$e);$row=$e.OriginalSource.DataContext;if(-not $row){return};$label=$e.OriginalSource.Content;if($label -eq 'AI分析'){try{$StatusText.Text='正在调用本地 Codex 分析…';$a=Invoke-MonitorCli @('analyze','--job',$row.JobUuid);$row.Analysis=$a;$row.Summary=$a.summary;$RecordsGrid.Items.Refresh();$StatusText.Text='AI分析完成'}catch{[Windows.MessageBox]::Show($_.Exception.Message,'AI分析失败','OK','Warning')}}elseif($label -eq '重试'){if([Windows.MessageBox]::Show("立即重试会直接调用影刀重试接口。若机器已有任务，可能导致等待或超时。`r`n`r`n确认重试：$($row.TaskName)？",'重试风险确认','YesNo','Warning') -eq 'Yes'){try{$result=Invoke-MonitorCli @('retry','--job',$row.JobUuid);[Windows.MessageBox]::Show("重试请求已受理，第 $($result.attempt) 次。",'已提交')}catch{[Windows.MessageBox]::Show($_.Exception.Message,'重试失败','OK','Error')}}}})
$RecordsGrid.AddHandler([Windows.Controls.Primitives.ToggleButton]::CheckedEvent,[Windows.RoutedEventHandler]{param($s,$e);if($e.OriginalSource.Name -eq 'SolvedCheck' -and $e.OriginalSource.DataContext -and ($e.OriginalSource.IsMouseOver -or $e.OriginalSource.IsKeyboardFocusWithin)){try{$null=Invoke-MonitorCli @('resolve','--job',$e.OriginalSource.DataContext.JobUuid,'--value','true');$e.OriginalSource.DataContext.Resolved=$true;$RecordsGrid.Items.Refresh()}catch{[Windows.MessageBox]::Show($_.Exception.Message,'更新失败','OK','Error');Load-Records}}})
$RecordsGrid.AddHandler([Windows.Controls.Primitives.ToggleButton]::UncheckedEvent,[Windows.RoutedEventHandler]{param($s,$e);if($e.OriginalSource.Name -eq 'SolvedCheck' -and $e.OriginalSource.DataContext -and ($e.OriginalSource.IsMouseOver -or $e.OriginalSource.IsKeyboardFocusWithin)){try{$null=Invoke-MonitorCli @('resolve','--job',$e.OriginalSource.DataContext.JobUuid,'--value','false');$e.OriginalSource.DataContext.Resolved=$false;$RecordsGrid.Items.Refresh()}catch{[Windows.MessageBox]::Show($_.Exception.Message,'更新失败','OK','Error');Load-Records}}})
$RecordsGrid.Add_PreviewMouseRightButtonDown({param($s,$e);$node=$e.OriginalSource;while($node -and -not ($node -is [Windows.Controls.DataGridRow])){$node=[Windows.Media.VisualTreeHelper]::GetParent($node)};if($node){$node.IsSelected=$true;$node.Focus();$RecordsGrid.SelectedItem=$node.Item}})
$TrashMenu.Add_Click({try{$r=$RecordsGrid.SelectedItem;if(-not $r){[Windows.MessageBox]::Show('请先选择一条异常记录。','放入回收站','OK','Information');return};if([Windows.MessageBox]::Show("将 $($r.TaskName) 放入回收站？",'确认','YesNo','Question') -ne 'Yes'){return};$null=Invoke-MonitorCli @('recycle','--job',$r.JobUuid);$RecordsGrid.SelectedItem=$null;Load-Records;$StatusText.Text='记录已放入回收站'}catch{[Windows.MessageBox]::Show($_.Exception.Message,'放入回收站失败','OK','Error');Load-Records}})
$RecycleButton.Add_Click({$rows=@(Invoke-MonitorCli @('data','--view','recycle'));$w=New-Object Windows.Window;$w.Title='异常回收站';$w.Width=850;$w.Height=520;$w.WindowStartupLocation='CenterOwner';$w.Owner=$window;$panel=New-Object Windows.Controls.DockPanel;$btn=New-Object Windows.Controls.Button;$btn.Content='恢复选中记录';$btn.Padding='12,7';[Windows.Controls.DockPanel]::SetDock($btn,'Top');$grid=New-Object Windows.Controls.DataGrid;$grid.IsReadOnly=$true;$grid.AutoGenerateColumns=$true;$grid.ItemsSource=@($rows|ForEach-Object{Convert-Row $_ $true});$panel.Children.Add($btn)|Out-Null;$panel.Children.Add($grid)|Out-Null;$w.Content=$panel;$btn.Add_Click({if($grid.SelectedItem){$null=Invoke-MonitorCli @('restore','--job',$grid.SelectedItem.JobUuid);$w.Close();Load-Records}});$w.ShowDialog()|Out-Null})
$ColumnsButton.Add_Click({$menu=New-Object Windows.Controls.ContextMenu;foreach($col in $RecordsGrid.Columns){$item=New-Object Windows.Controls.MenuItem;$item.Header=$col.Header;$item.IsCheckable=$true;$item.IsChecked=$col.Visibility -eq 'Visible';$item.Tag=$col;$item.Add_Click({$this.Tag.Visibility=if($this.IsChecked){'Visible'}else{'Collapsed'};$script:Settings.hidden_columns=@($RecordsGrid.Columns|Where-Object{$_.Visibility -ne 'Visible'}|ForEach-Object{[string]$_.Header});$json=$script:Settings|ConvertTo-Json -Depth 8 -Compress;$script:Settings=Invoke-MonitorCli @('settings-save',$json)});$menu.Items.Add($item)|Out-Null};$menu.IsOpen=$true})

$notify=New-Object Windows.Forms.NotifyIcon;$notify.Icon=[Drawing.SystemIcons]::Information;$notify.Text='RPA 异常闭环控制台';$notify.Visible=$true
$trayMenu=New-Object Windows.Forms.ContextMenuStrip;$showItem=$trayMenu.Items.Add('打开控制台');$pauseItem=$trayMenu.Items.Add('暂停/继续巡检');$exitItem=$trayMenu.Items.Add('退出程序');$notify.ContextMenuStrip=$trayMenu
$showAction={ $window.Show();$window.WindowState='Normal';$window.Activate() };$showItem.Add_Click($showAction);$notify.Add_DoubleClick($showAction);$pauseItem.Add_Click({$PauseButton.RaiseEvent((New-Object Windows.RoutedEventArgs([Windows.Controls.Button]::ClickEvent)))})
$exitItem.Add_Click({$script:ExitRequested=$true;$notify.Visible=$false;$window.Close()})
$window.Add_Closing({param($s,$e);if(-not $script:ExitRequested){$e.Cancel=$true;$window.Hide();$notify.ShowBalloonTip(2000,'RPA异常闭环控制台','控制台已缩到后台，巡检仍会继续运行。','Info')}})
$window.Add_Closed({$notify.Dispose()})

$timer=New-Object Windows.Threading.DispatcherTimer;$timer.Interval=[TimeSpan]::FromSeconds(30);$timer.Add_Tick({if(-not $script:Settings.paused -and $script:NextDue -is [datetime] -and (Get-Date) -ge $script:NextDue){try{$result=Invoke-MonitorCli @('scan');if($result.notifications){$id=($result.updatedAt+[string]$result.notifications.Count);if($id-ne$script:LastNotice){$script:LastNotice=$id;$notify.ShowBalloonTip(5000,'RPA异常更新',($result.notifications[0].message),'Warning')}};Load-Records}catch{$StatusText.Text="巡检失败：$($_.Exception.Message)"};Reset-NextDue}});$timer.Start()

try { Load-Settings; Reset-NextDue; Load-Records } catch { [Windows.MessageBox]::Show($_.Exception.Message,'启动失败','OK','Error') }
if ($StartHidden) { $window.Add_ContentRendered({$window.Hide()}) }
$null=$window.ShowDialog()
