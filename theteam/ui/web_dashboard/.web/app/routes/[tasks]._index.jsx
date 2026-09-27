import {Card as RadixThemesCard,Flex as RadixThemesFlex,Heading as RadixThemesHeading,Separator as RadixThemesSeparator,Table as RadixThemesTable,Text as RadixThemesText} from "@radix-ui/themes"
import {Badge_badge_138208de3c56e0bf7ea967ec9dd62aea_890f0220,Bare_comp_c526c83af419243066512b4e1264df8f_890f0220,Bare_comp_c5f5eccbf55e9168e629bd271863a762_890f0220,Bare_comp_c87a43ab58f6bef27a66000b36cdaca6_890f0220,Bare_comp_f2e79dd604d294f927721a9f529ea19a_890f0220,Button_button_e24623ba4255c629ae1cf3b08abac8a8_890f0220,Cond_comp_75d8039380d4ce8d0b67edca458673f5_890f0220,Cond_comp_86c543f52c38cd3198fb6db46172a00c_890f0220,Cond_comp_ec3dc2bd15657244c860bf48aa0053c7_890f0220,Container_container_a053053593036a0493517480ad7782c5_890f0220,Foreach_comp_642f51fc4f791ed369e871ebfbdcc38b_890f0220,Foreach_comp_eda8b980ce787cd763c4b58767de9222_890f0220} from "$/app_components/theteam_dashboard/pages/tasks"
import {Fragment,useEffect} from "react"
import {jsx} from "@emotion/react"





function Component() {





  return (
    jsx(Fragment,{},jsx(Container_container_a053053593036a0493517480ad7782c5_890f0220,{},jsx(RadixThemesFlex,{align:"start",className:"rx-Stack",css:({ ["width"] : "100%" }),direction:"column",gap:"4"},jsx(RadixThemesFlex,{align:"start",className:"rx-Stack",css:({ ["width"] : "100%", ["padding"] : "4" }),direction:"row",justify:"between",gap:"3"},jsx(RadixThemesHeading,{size:"6"},"Task Management"),jsx(Button_button_e24623ba4255c629ae1cf3b08abac8a8_890f0220,{},"Refresh")),jsx(RadixThemesSeparator,{size:"4"},),jsx(RadixThemesCard,{css:({ ["padding"] : "4", ["width"] : "100%" })},jsx(RadixThemesFlex,{align:"start",className:"rx-Stack",direction:"column",gap:"2"},jsx(RadixThemesHeading,{size:"5"},"Scheduled Tasks"),jsx(Fragment,{},jsx(Cond_comp_ec3dc2bd15657244c860bf48aa0053c7_890f0220,{},jsx(Fragment,{},jsx(RadixThemesTable.Root,{variant:"surface"},jsx(RadixThemesTable.Header,{},jsx(RadixThemesTable.Row,{},jsx(RadixThemesTable.ColumnHeaderCell,{},"Task"),jsx(RadixThemesTable.ColumnHeaderCell,{},"Interval"),jsx(RadixThemesTable.ColumnHeaderCell,{},"Next Run"))),jsx(RadixThemesTable.Body,{},jsx(Foreach_comp_642f51fc4f791ed369e871ebfbdcc38b_890f0220,{},)))),jsx(Fragment,{},jsx(RadixThemesText,{as:"p",css:({ ["color"] : "var(--gray-9)" }),size:"3"},"No scheduled tasks")))))),jsx(RadixThemesCard,{css:({ ["padding"] : "4", ["width"] : "100%" })},jsx(RadixThemesFlex,{align:"start",className:"rx-Stack",direction:"column",gap:"2"},jsx(RadixThemesHeading,{size:"5"},"Daemon Status"),jsx(RadixThemesFlex,{align:"start",className:"rx-Stack",direction:"row",gap:"2"},jsx(RadixThemesText,{as:"p",weight:"bold"},"Status: "),jsx(Badge_badge_138208de3c56e0bf7ea967ec9dd62aea_890f0220,{},jsx(Bare_comp_c526c83af419243066512b4e1264df8f_890f0220,{},))),jsx(RadixThemesText,{as:"p",size:"2"},jsx(Bare_comp_c87a43ab58f6bef27a66000b36cdaca6_890f0220,{},)),jsx(RadixThemesText,{as:"p",size:"2"},jsx(Bare_comp_c5f5eccbf55e9168e629bd271863a762_890f0220,{},)),jsx(Fragment,{},jsx(Cond_comp_86c543f52c38cd3198fb6db46172a00c_890f0220,{},jsx(Fragment,{},jsx(RadixThemesText,{as:"p",size:"2"},jsx(Bare_comp_f2e79dd604d294f927721a9f529ea19a_890f0220,{},))),jsx(Fragment,{},))))),jsx(RadixThemesCard,{css:({ ["padding"] : "4", ["width"] : "100%" })},jsx(RadixThemesFlex,{align:"start",className:"rx-Stack",direction:"column",gap:"2"},jsx(RadixThemesHeading,{size:"5"},"All Registered Tasks"),jsx(Fragment,{},jsx(Cond_comp_75d8039380d4ce8d0b67edca458673f5_890f0220,{},jsx(Fragment,{},jsx(RadixThemesTable.Root,{variant:"surface"},jsx(RadixThemesTable.Header,{},jsx(RadixThemesTable.Row,{},jsx(RadixThemesTable.ColumnHeaderCell,{},"ID"),jsx(RadixThemesTable.ColumnHeaderCell,{},"Name"),jsx(RadixThemesTable.ColumnHeaderCell,{},"Type"),jsx(RadixThemesTable.ColumnHeaderCell,{},"Priority"),jsx(RadixThemesTable.ColumnHeaderCell,{},"Schedule"))),jsx(RadixThemesTable.Body,{},jsx(Foreach_comp_eda8b980ce787cd763c4b58767de9222_890f0220,{},)))),jsx(Fragment,{},jsx(RadixThemesText,{as:"p",css:({ ["color"] : "var(--gray-9)" }),size:"3"},"No tasks registered")))))))),jsx("title",{},"Task Management"),jsx("meta",{content:"favicon.ico",property:"og:image"},))
  )
}
Component.displayName = "Component(tasks)";

export default Component;
