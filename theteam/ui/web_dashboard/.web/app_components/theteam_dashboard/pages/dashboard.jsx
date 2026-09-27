
import {ReflexEvent,applyEventActions,isTrue} from "$/utils/state"
import {StateContexts,addEvents} from "$/utils/context"
import {Fragment,memo,useCallback,useContext,useEffect} from "react"
import {jsx} from "@emotion/react"
import {Badge as RadixThemesBadge,Button as RadixThemesButton,Container as RadixThemesContainer,Flex as RadixThemesFlex,Text as RadixThemesText} from "@radix-ui/themes"








export const Bare_comp_05bb951f8038d34a98e66f97a60e6e9b_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam_dashboard___state____dashboard_state = useContext(StateContexts.reflex___state____state__theteam_dashboard___state____dashboard_state)



    return(
        (reflex___state____state__theteam_dashboard___state____dashboard_state.connection_ok_rx_state_ ? "Connected" : "Disconnected")
    )
});
Bare_comp_05bb951f8038d34a98e66f97a60e6e9b_972591b5.displayName = "Bare";

export const Badge_badge_3ab68095d652e334334c4436c0223d9c_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam_dashboard___state____dashboard_state = useContext(StateContexts.reflex___state____state__theteam_dashboard___state____dashboard_state)



    return(
        jsx(RadixThemesBadge,{color:(reflex___state____state__theteam_dashboard___state____dashboard_state.connection_ok_rx_state_ ? "green" : "red"),variant:"solid"},children)
    )
});
Badge_badge_3ab68095d652e334334c4436c0223d9c_972591b5.displayName = "Badge";

export const Bare_comp_fc493bd61c55220040c5013939d9ff1f_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam_dashboard___state____dashboard_state = useContext(StateContexts.reflex___state____state__theteam_dashboard___state____dashboard_state)



    return(
        reflex___state____state__theteam_dashboard___state____dashboard_state.task_count_rx_state_
    )
});
Bare_comp_fc493bd61c55220040c5013939d9ff1f_972591b5.displayName = "Bare";

export const Bare_comp_184c410ce64104ba8e84f3b93d847916_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam_dashboard___state____dashboard_state = useContext(StateContexts.reflex___state____state__theteam_dashboard___state____dashboard_state)



    return(
        reflex___state____state__theteam_dashboard___state____dashboard_state.scheduled_count_rx_state_
    )
});
Bare_comp_184c410ce64104ba8e84f3b93d847916_972591b5.displayName = "Bare";

export const Bare_comp_c526c83af419243066512b4e1264df8f_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam_dashboard___state____dashboard_state = useContext(StateContexts.reflex___state____state__theteam_dashboard___state____dashboard_state)



    return(
        reflex___state____state__theteam_dashboard___state____dashboard_state.daemon_running_text_rx_state_
    )
});
Bare_comp_c526c83af419243066512b4e1264df8f_972591b5.displayName = "Bare";

export const Text_text_9185136b0bfdfc73c97f7be7b826f92f_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam_dashboard___state____dashboard_state = useContext(StateContexts.reflex___state____state__theteam_dashboard___state____dashboard_state)



    return(
        jsx(RadixThemesText,{as:"p",css:({ ["color"] : ("var(--"+((reflex___state____state__theteam_dashboard___state____dashboard_state.daemon_running_text_rx_state_?.valueOf?.() === "Running"?.valueOf?.()) ? "green" : "orange")+"-8)") }),size:"8",weight:"bold"},children)
    )
});
Text_text_9185136b0bfdfc73c97f7be7b826f92f_972591b5.displayName = "Text";

export const Bare_comp_1c67db3749b827f8a9678a75ad085f30_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam_dashboard___state____dashboard_state = useContext(StateContexts.reflex___state____state__theteam_dashboard___state____dashboard_state)



    return(
        reflex___state____state__theteam_dashboard___state____dashboard_state.daemon_last_check_text_rx_state_
    )
});
Bare_comp_1c67db3749b827f8a9678a75ad085f30_972591b5.displayName = "Bare";

export const Bare_comp_59c552d8772c3f736d02643c958351d2_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        (isTrue(reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.health_row_rx_state_?.["icon"]) ? reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.health_row_rx_state_?.["icon"] : "")
    )
});
Bare_comp_59c552d8772c3f736d02643c958351d2_972591b5.displayName = "Bare";

export const Text_text_26a8c86dbad30fcf21911514274bda5d_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        jsx(RadixThemesText,{as:"p",css:({ ["color"] : (isTrue(reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.health_row_rx_state_?.["color"]) ? reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.health_row_rx_state_?.["color"] : "gray") }),size:"3"},children)
    )
});
Text_text_26a8c86dbad30fcf21911514274bda5d_972591b5.displayName = "Text";

export const Bare_comp_a385d9d6f3322f68c93882fd00050727_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        (isTrue(reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.health_row_rx_state_?.["percent"]) ? reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.health_row_rx_state_?.["percent"] : "0%")
    )
});
Bare_comp_a385d9d6f3322f68c93882fd00050727_972591b5.displayName = "Bare";

export const Bare_comp_b9685d46b8038cef8d4d08d02492176c_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        (isTrue(reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.health_row_rx_state_?.["label"]) ? reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.health_row_rx_state_?.["label"] : "Unknown")
    )
});
Bare_comp_b9685d46b8038cef8d4d08d02492176c_972591b5.displayName = "Bare";

export const Badge_badge_983f3504f78ede30bb134a9660833f25_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        jsx(RadixThemesBadge,{css:({ ["color"] : (isTrue(reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.health_row_rx_state_?.["color"]) ? reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.health_row_rx_state_?.["color"] : "gray") }),variant:"soft"},children)
    )
});
Badge_badge_983f3504f78ede30bb134a9660833f25_972591b5.displayName = "Badge";

export const Cond_comp_50a3dd4686756e4519a56130e7246b5d_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        ((Object.keys(reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.health_row_rx_state_ ?? {}).length > 0)?(children?.at?.(0)):(children?.at?.(1)))
    )
});
Cond_comp_50a3dd4686756e4519a56130e7246b5d_972591b5.displayName = "Cond";

export const Foreach_comp_2ec2825aeac980d66eef7fc6764f4613_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        Array.prototype.map.call(reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.breaker_rows_rx_state_ ?? [],((b_rx_state_,index_37ff7f0cdce564715cecf2663615e52e)=>(jsx(RadixThemesFlex,{align:"center",className:"rx-Stack",css:({ ["width"] : "100%" }),direction:"row",justify:"between",key:index_37ff7f0cdce564715cecf2663615e52e,gap:"2"},jsx(RadixThemesText,{as:"p",size:"2",weight:"medium"},b_rx_state_?.["name"]),jsx(RadixThemesBadge,{css:({ ["color"] : b_rx_state_?.["color"] }),size:"1",variant:"soft"},(b_rx_state_?.["icon"]+" "+b_rx_state_?.["label"])),jsx(RadixThemesText,{as:"p",color:"gray",size:"1"},(b_rx_state_?.["failures"]+"/"+b_rx_state_?.["threshold"]+" failures"))))))
    )
});
Foreach_comp_2ec2825aeac980d66eef7fc6764f4613_972591b5.displayName = "Foreach";

export const Cond_comp_075139e2fd20aa03b03374ef9a672ebc_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        ((reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.breaker_rows_rx_state_.length > 0)?(children?.at?.(0)):(children?.at?.(1)))
    )
});
Cond_comp_075139e2fd20aa03b03374ef9a672ebc_972591b5.displayName = "Cond";

export const Bare_comp_a79c34f5d3e133456eea499f8889a534_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        (reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.health_recovery_open_rx_state_ ? "\u25bc" : "\u25b6")
    )
});
Bare_comp_a79c34f5d3e133456eea499f8889a534_972591b5.displayName = "Bare";

export const Button_button_f51d078eb94a78c9f701d2c14b43f742_972591b5 = memo(({children}) => {
    const on_click_c58de463e424cca6d090162def732e34 = useCallback(((_e) => (addEvents([(ReflexEvent("reflex___state____state.theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.toggle_health_recovery", ({  }), ({  })))], [_e], ({  })))), [addEvents, ReflexEvent])



    return(
        jsx(RadixThemesButton,{onClick:on_click_c58de463e424cca6d090162def732e34,size:"1",variant:"ghost"},children)
    )
});
Button_button_f51d078eb94a78c9f701d2c14b43f742_972591b5.displayName = "Button";

export const Bare_comp_5c7b56badda2740628103619c36ca8ae_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.recovery_summary_rx_state_
    )
});
Bare_comp_5c7b56badda2740628103619c36ca8ae_972591b5.displayName = "Bare";

export const Bare_comp_874662093b2a257ed699484459bc0a7c_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.recovery_lines_rx_state_
    )
});
Bare_comp_874662093b2a257ed699484459bc0a7c_972591b5.displayName = "Bare";

export const Cond_comp_3e36b85fa9792b2172a622c0be90892e_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        (reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.health_recovery_open_rx_state_?(children?.at?.(0)):(children?.at?.(1)))
    )
});
Cond_comp_3e36b85fa9792b2172a622c0be90892e_972591b5.displayName = "Cond";

export const Cond_comp_2eab7973150fd67d5ed2b6a5eb043baf_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        ((reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.recovery_rows_rx_state_.length > 0)?(children?.at?.(0)):(children?.at?.(1)))
    )
});
Cond_comp_2eab7973150fd67d5ed2b6a5eb043baf_972591b5.displayName = "Cond";

export const Bare_comp_eb703c59942e9237dd709ff7a2db5aae_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam_dashboard___state____dashboard_state = useContext(StateContexts.reflex___state____state__theteam_dashboard___state____dashboard_state)



    return(
        (reflex___state____state__theteam_dashboard___state____dashboard_state.critical_folders_ok_rx_state_ ? "OK" : "Needs attention")
    )
});
Bare_comp_eb703c59942e9237dd709ff7a2db5aae_972591b5.displayName = "Bare";

export const Badge_badge_6432e0bf15223a909f0a27a8baa08255_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam_dashboard___state____dashboard_state = useContext(StateContexts.reflex___state____state__theteam_dashboard___state____dashboard_state)



    return(
        jsx(RadixThemesBadge,{color:(reflex___state____state__theteam_dashboard___state____dashboard_state.critical_folders_ok_rx_state_ ? "green" : "orange")},children)
    )
});
Badge_badge_6432e0bf15223a909f0a27a8baa08255_972591b5.displayName = "Badge";

export const Bare_comp_7bcf45c455b6c273e62a23138993a7b5_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam_dashboard___state____dashboard_state = useContext(StateContexts.reflex___state____state__theteam_dashboard___state____dashboard_state)



    return(
        ("Root clutter: "+reflex___state____state__theteam_dashboard___state____dashboard_state.root_clutter_rx_state_+" items")
    )
});
Bare_comp_7bcf45c455b6c273e62a23138993a7b5_972591b5.displayName = "Bare";

export const Bare_comp_5b6e8c8cbadc1569f2921e5731d39a8d_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.metrics_summary_rx_state_
    )
});
Bare_comp_5b6e8c8cbadc1569f2921e5731d39a8d_972591b5.displayName = "Bare";

export const Foreach_comp_e4f373a407e3f51d7e890084fbecc49c_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        Array.prototype.map.call(reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.metrics_rows_rx_state_ ?? [],((m_rx_state_,index_d840c3362868ea2bdcd7b5dfd47e7779)=>(jsx(RadixThemesFlex,{align:"center",className:"rx-Stack",css:({ ["width"] : "100%" }),direction:"row",justify:"between",key:index_d840c3362868ea2bdcd7b5dfd47e7779,gap:"2"},jsx(RadixThemesText,{as:"p",size:"2",weight:"medium"},m_rx_state_?.["name"]),jsx(RadixThemesText,{as:"p",color:"gray",size:"1"},m_rx_state_?.["label"]),jsx(RadixThemesText,{as:"p",size:"2",weight:"bold"},m_rx_state_?.["display"])))))
    )
});
Foreach_comp_e4f373a407e3f51d7e890084fbecc49c_972591b5.displayName = "Foreach";

export const Cond_comp_e1eb565895daade57973b2dac06ea974_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state = useContext(StateContexts.reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state)



    return(
        ((reflex___state____state__theteam___ui___web_dashboard___theteam_dashboard___visibility_state____visibility_state.metrics_rows_rx_state_.length > 0)?(children?.at?.(0)):(children?.at?.(1)))
    )
});
Cond_comp_e1eb565895daade57973b2dac06ea974_972591b5.displayName = "Cond";

export const Foreach_comp_4edfba0efe98387dddcff119d9cb57b7_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam_dashboard___state____dashboard_state = useContext(StateContexts.reflex___state____state__theteam_dashboard___state____dashboard_state)



    return(
        Array.prototype.map.call(reflex___state____state__theteam_dashboard___state____dashboard_state.execution_log_rx_state_ ?? [],((entry_rx_state_,index_831fff14efb8ac41fb6e43823a755705)=>(jsx(RadixThemesFlex,{align:"start",className:"rx-Stack",direction:"row",key:index_831fff14efb8ac41fb6e43823a755705,gap:"4"},jsx(RadixThemesText,{as:"p",size:"2",weight:"bold"},(isTrue(entry_rx_state_?.["task_id"]) ? entry_rx_state_?.["task_id"] : "unknown")),jsx(RadixThemesBadge,{color:(isTrue((isTrue(entry_rx_state_?.["overall_success"]) ? entry_rx_state_?.["overall_success"] : false)) ? "green" : "red")},(isTrue((isTrue(entry_rx_state_?.["overall_success"]) ? entry_rx_state_?.["overall_success"] : false)) ? "Success" : "Failed")),jsx(RadixThemesText,{as:"p",css:({ ["color"] : "var(--gray-9)" }),size:"1"},(isTrue(entry_rx_state_?.["timestamp_short"]) ? entry_rx_state_?.["timestamp_short"] : ""))))))
    )
});
Foreach_comp_4edfba0efe98387dddcff119d9cb57b7_972591b5.displayName = "Foreach";

export const Cond_comp_dae081dd860204a3da126c0bd95bb3c0_972591b5 = memo(({children}) => {
    const reflex___state____state__theteam_dashboard___state____dashboard_state = useContext(StateContexts.reflex___state____state__theteam_dashboard___state____dashboard_state)



    return(
        ((reflex___state____state__theteam_dashboard___state____dashboard_state.execution_log_rx_state_.length > 0)?(children?.at?.(0)):(children?.at?.(1)))
    )
});
Cond_comp_dae081dd860204a3da126c0bd95bb3c0_972591b5.displayName = "Cond";

export const Container_container_a053053593036a0493517480ad7782c5_972591b5 = memo(({children}) => {
    
                useEffect(() => {
                    ((...args) => (addEvents([(ReflexEvent("reflex___state____state.theteam_dashboard___state____dashboard_state.load_all", ({  }), ({  })))], args, ({  }))))()
                    return () => {
                        
                    }
                }, []);



    return(
        jsx(RadixThemesContainer,{css:({ ["padding"] : "4", ["maxWidth"] : "1200px" }),size:"3"},children)
    )
});
Container_container_a053053593036a0493517480ad7782c5_972591b5.displayName = "Container";
