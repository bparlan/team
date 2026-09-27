import {Badge as RadixThemesBadge,Card as RadixThemesCard,Container as RadixThemesContainer,Flex as RadixThemesFlex,Heading as RadixThemesHeading,Separator as RadixThemesSeparator,Text as RadixThemesText} from "@radix-ui/themes"
import {Bare_comp_4b3b16e87c190445f30857701e8009db_f07d054b,Button_button_29078524021c1baca479c0783c1bd0f3_f07d054b,Cond_comp_7be270fa9e8c54ab8529246d9c46cdbc_f07d054b,Cond_comp_fb43cbfe5b1455f80e6f3346f0bf1e72_f07d054b,Foreach_comp_438b180396710c68fc60ebbbe46f0e2c_f07d054b,Foreach_comp_4a2493f58227d62270a322063eb62ae2_f07d054b} from "$/app_components/theteam_dashboard/pages/agents"
import {Fragment,useEffect} from "react"
import {jsx} from "@emotion/react"





function Component() {





  return (
    jsx(Fragment,{},jsx(RadixThemesContainer,{css:({ ["padding"] : "4", ["maxWidth"] : "1200px" }),size:"3"},jsx(RadixThemesFlex,{align:"start",className:"rx-Stack",css:({ ["width"] : "100%" }),direction:"column",gap:"4"},jsx(RadixThemesFlex,{align:"start",className:"rx-Stack",css:({ ["width"] : "100%", ["padding"] : "4" }),direction:"row",justify:"between",gap:"3"},jsx(RadixThemesHeading,{size:"6"},"Agent Roster"),jsx(RadixThemesBadge,{color:"blue",variant:"soft"},jsx(Bare_comp_4b3b16e87c190445f30857701e8009db_f07d054b,{},)),jsx(Button_button_29078524021c1baca479c0783c1bd0f3_f07d054b,{},"Collapse all")),jsx(RadixThemesSeparator,{size:"4"},),jsx(RadixThemesCard,{css:({ ["padding"] : "4", ["width"] : "100%" })},jsx(RadixThemesFlex,{align:"start",className:"rx-Stack",css:({ ["width"] : "100%" }),direction:"column",gap:"3"},jsx(RadixThemesHeading,{size:"5"},"Agents"),jsx(Fragment,{},jsx(Cond_comp_7be270fa9e8c54ab8529246d9c46cdbc_f07d054b,{},jsx(Fragment,{},jsx(Foreach_comp_4a2493f58227d62270a322063eb62ae2_f07d054b,{},)),jsx(Fragment,{},jsx(RadixThemesText,{as:"p",color:"gray",size:"3"},"No agents registered")))))),jsx(RadixThemesCard,{css:({ ["padding"] : "4", ["width"] : "100%" })},jsx(RadixThemesFlex,{align:"start",className:"rx-Stack",css:({ ["width"] : "100%" }),direction:"column",gap:"3"},jsx(RadixThemesHeading,{size:"5"},"Recent Contributions"),jsx(Fragment,{},jsx(Cond_comp_fb43cbfe5b1455f80e6f3346f0bf1e72_f07d054b,{},jsx(Fragment,{},jsx(Foreach_comp_438b180396710c68fc60ebbbe46f0e2c_f07d054b,{},)),jsx(Fragment,{},jsx(RadixThemesText,{as:"p",color:"gray",size:"3"},"No contributions yet")))))))),jsx("title",{},"Agent Roster"),jsx("meta",{content:"favicon.ico",property:"og:image"},))
  )
}
Component.displayName = "Component(agents)";

export default Component;
