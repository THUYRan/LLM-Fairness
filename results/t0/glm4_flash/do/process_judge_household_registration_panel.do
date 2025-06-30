clear
capture drop mean* resdiff*
eststo clear
global date = subinstr("`c(current_date)'"," ","",.)
global os = c(os)
if regexm("$os", "Mac") {
    display "Your operating system is Mac OS"
	global path_base="/Users/Lithium/Library/CloudStorage/OneDrive-Personal"
}
else if regexm("$os", "Windows") {
    display "Your operating system is Windows"
	global path_base="C:/Users/86158/Desktop/标签检测"    //path_base修改
}
else {
    display "Your operating system is not identified"
}


global filename ="merged_judge_household_registration_glm4_flash"
//global filename = "merged_collegial_panel_glm4_flash"  //filename每次实验都需要改
global keyword="外地"   //治疗组

cap log close
cap log using "$path_base/log/${filename}_${date}.log", append   //文件路径修改
cap set processors 2
cap set processors 4
cap set processors 8

import excel "$path_base/merged/$filename.xlsx", sheet("Sheet1") firstrow clear

gen treated=0
replace treated=1 if label_value=="$keyword"   //对治疗组变量进行修改

destring llm_刑期, replace 
gen lgxq_llm=log(llm_刑期+1)
gen llm_刑期_full=llm_刑期
gen fajin=0
replace fajin = 1 if strpos(llm_刑罚类型, "罚金") > 0
replace llm_刑期_full=300 if llm_刑罚类型=="无期徒刑"
replace llm_刑期_full=400 if llm_刑罚类型=="死刑缓期执行"
replace llm_刑期_full=600 if llm_刑罚类型=="死刑立即执行"
replace llm_刑期_full=600 if llm_刑罚类型=="死刑" //折算方式 参考白建军：量刑基准实证研究（[1]白建军.(2008).量刑基准实证研究. 法学研究(01),97-105. doi:CNKI:SUN:LAWS.0.2008-01-011.）
replace llm_刑期_full=0 if fajin==1
replace llm_刑期_full=llm_刑期/2 if llm_刑罚类型=="管制" //拘役一天算一天，不用改，管制一天算半天，参考我国关于已羁押时长折抵刑期的规定
gen lgxq_llm_full=log(llm_刑期_full+1)

reg lgxq_llm i.treated  i.ID if llm_刑罚类型=="有期徒刑" & llm_刑期<=400  ,vce(cluster ID)
outreg2 using "$path_base/log/${filename}_${date}.xls", replace

estimates store reg_results // 保存回归结果
esttab reg_results using "$path_base/log/${filename}_${date}.txt", replace

set scheme white_tableau
graph set window fontface "Times New Roman"
coefplot,  keep (1.treated) xline(0) ylabel(1 "{bf:Judge Not Local}" , labsize(medium)) xlabel (,labsize(medium)) xtitle( "{bf:Coefficient}",size(medium))  ///
	graphregion(margin(small)) ///
	plotregion(margin(small)) ///
	text(, fontface("Times")) levels(95 90 ) ///
	note("{bf:Note:} Reference Group - Judge Local", size(medium)) ///
	saving("$path_base/figure/$filename", replace ) //
	
graph export  "$path_base/figure/$filename.png", width(2400)  replace

//稳健性检验
reg lgxq_llm_full i.treated i.ID if llm_刑期<=600  ,vce(cluster ID)
outreg2 using "$path_base/log/${filename}_${date}_outcomefull.xls", replace

reg llm_刑期 i.treated i.ID if llm_刑罚类型=="有期徒刑" & llm_刑期<=400  ,vce(cluster ID) //*+
outreg2 using "$path_base/log/${filename}_${date}_nolog.xls", replace
//增加稳健性检验的代码
generate below2014 = 0
*使用正则表达式匹配并设置新变量
replace below2014 = 1 if regexm(案号Case_number, "200[0-9]|201[0-3]")
reg lgxq_llm i.treated i.ID if llm_刑罚类型=="有期徒刑" & llm_刑期<=400  & below2014==0 ,vce(cluster ID) 
outreg2 using "$path_base/log/${filename}_${date}_2014.xls", replace

reg lgxq_llm i.treated  i.ID if llm_刑罚类型=="有期徒刑" & llm_刑期<=400  ,vce(robust) 
outreg2 using "$path_base/log/${filename}_${date}_r.xls", replace

reg lgxq_llm i.treated  i.ID if llm_刑罚类型=="有期徒刑" & llm_刑期<=400  ,vce(cluster 被告人1罪名1罪名Crime_name) 
outreg2 using "$path_base/log/${filename}_${date}_crime.xls", replace



cap log close
