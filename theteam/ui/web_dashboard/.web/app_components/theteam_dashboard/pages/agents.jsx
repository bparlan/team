
import {ReflexEvent,applyEventActions,isTrue} from "$/utils/state"
import {StateContexts,addEvents} from "$/utils/context"
import {Fragment,memo,useCallback,useContext,useEffect} from "react"
import {jsx} from "@emotion/react"
import {Badge as RadixThemesBadge,Button as RadixThemesButton,Flex as RadixThemesFlex,Text as RadixThemesText} from "@radix-ui/themes"








export const Bare_comp_4b3b16e87c190445f30857701e8009db_f07d054b = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.roster_summary_rx_state_
    )
});
Bare_comp_4b3b16e87c190445f30857701e8009db_f07d054b.displayName = "Bare";

export const Button_button_29078524021c1baca479c0783c1bd0f3_f07d054b = memo(({children}) => {
    const on_click_7a990df60fc44ef6396383465fa3f76d = useCallback(((_e) => (addEvents([(ReflexEvent("reflex___state____state.theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.collapse_all", ({  }), ({  })))], [_e], ({  })))), [addEvents, ReflexEvent])



    return(
        jsx(RadixThemesButton,{onClick:on_click_7a990df60fc44ef6396383465fa3f76d,size:"1",variant:"ghost"},children)
    )
});
Button_button_29078524021c1baca479c0783c1bd0f3_f07d054b.displayName = "Button";

export const Foreach_comp_4a2493f58227d62270a322063eb62ae2_f07d054b = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        Array.prototype.map.call(reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.roster_view_rx_state_ ?? [],((agent_rx_state_,index_9e7dc13d6c7fa41addd66a07442ae2d7)=>(jsx(RadixThemesFlex,{align:"start",className:"rx-Stack",css:({ ["width"] : "100%", ["paddingTop"] : "3", ["paddingBottom"] : "3" }),direction:"column",key:index_9e7dc13d6c7fa41addd66a07442ae2d7,gap:"1"},jsx(RadixThemesFlex,{align:"center",className:"rx-Stack",css:({ ["width"] : "100%" }),direction:"row",gap:"3"},jsx(RadixThemesText,{as:"p",css:({ ["color"] : agent_rx_state_?.["status_color"] }),size:"3"},agent_rx_state_?.["status_icon"]),jsx(RadixThemesFlex,{align:"start",className:"rx-Stack",direction:"column",gap:"0"},jsx(RadixThemesText,{as:"p",size:"2",weight:"bold"},agent_rx_state_?.["name"]),jsx(RadixThemesText,{as:"p",color:"gray",size:"1"},agent_rx_state_?.["role"])),jsx(RadixThemesBadge,{css:({ ["color"] : agent_rx_state_?.["status_color"] }),size:"1",variant:"soft"},agent_rx_state_?.["status_label"])),jsx(RadixThemesFlex,{align:"start",className:"rx-Stack",direction:"row",gap:"3"},jsx(RadixThemesText,{as:"p",color:"gray",size:"1"},agent_rx_state_?.["completed_label"]),jsx(RadixThemesText,{as:"p",color:"gray",size:"1"},agent_rx_state_?.["failed_label"]),jsx(RadixThemesText,{as:"p",color:"gray",size:"1"},agent_rx_state_?.["success_label"])),jsx(Fragment,{},(isTrue(agent_rx_state_?.["has_details"])?(jsx(Fragment,{},jsx(RadixThemesFlex,{align:"start",className:"rx-Stack",css:({ ["width"] : "100%" }),direction:"column",gap:"1"},jsx(RadixThemesButton,{onClick:((_e) => (addEvents([(ReflexEvent("reflex___state____state.theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.toggle_panel", ({ ["panel_id"] : agent_rx_state_?.["panel_id"] }), ({  })))], [_e], ({  })))),size:"1",variant:"ghost"},(isTrue(agent_rx_state_?.["is_open"]) ? "\u25bc" : "\u25b6")),jsx(RadixThemesText,{as:"p",size:"2",weight:"bold"},"Contribution feed"),jsx(RadixThemesText,{as:"p",color:"gray",size:"1"},agent_rx_state_?.["detail_label"]),jsx(Fragment,{},(isTrue(agent_rx_state_?.["is_open"])?(jsx(Fragment,{},jsx(RadixThemesText,{as:"p",color:"gray",css:({ ["whiteSpace"] : "pre-line" }),size:"1"},agent_rx_state_?.["detail_text"]))):(jsx(Fragment,{},))))))):(jsx(Fragment,{},))))))))
    )
});
Foreach_comp_4a2493f58227d62270a322063eb62ae2_f07d054b.displayName = "Foreach";

export const Cond_comp_7be270fa9e8c54ab8529246d9c46cdbc_f07d054b = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        ((reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.roster_view_rx_state_.length > 0)?(children?.at?.(0)):(children?.at?.(1)))
    )
});
Cond_comp_7be270fa9e8c54ab8529246d9c46cdbc_f07d054b.displayName = "Cond";

export const Foreach_comp_438b180396710c68fc60ebbbe46f0e2c_f07d054b = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        Array.prototype.map.call(reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.contribution_feed_rx_state_ ?? [],((c_rx_state_,index_5e1cd4e72e9eb8dc362f2989792cf73c)=>(jsx(RadixThemesFlex,{align:"center",className:"rx-Stack",css:({ ["width"] : "100%" }),direction:"row",key:index_5e1cd4e72e9eb8dc362f2989792cf73c,gap:"2"},jsx(RadixThemesBadge,{size:"1",variant:"soft"},c_rx_state_?.["agent"]),jsx(RadixThemesText,{as:"p",size:"2"},c_rx_state_?.["task"]),jsx(RadixThemesBadge,{color:((c_rx_state_?.["status"]?.valueOf?.() === "completed"?.valueOf?.()) ? "green" : "red"),size:"1",variant:"soft"},c_rx_state_?.["status"])))))
    )
});
Foreach_comp_438b180396710c68fc60ebbbe46f0e2c_f07d054b.displayName = "Foreach";

export const Cond_comp_fb43cbfe5b1455f80e6f3346f0bf1e72_f07d054b = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        ((reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.contribution_feed_rx_state_.length > 0)?(children?.at?.(0)):(children?.at?.(1)))
    )
});
Cond_comp_fb43cbfe5b1455f80e6f3346f0bf1e72_f07d054b.displayName = "Cond";
