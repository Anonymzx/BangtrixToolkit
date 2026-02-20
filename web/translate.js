import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "BangtrixTranslatePro",

    async setup() {
        app.ui.settings.addSetting({
            id: "bangtrix_translate_window",
            name: "Open Bangtrix Translate Window",
            type: "button",
            onClick: () => {
                window.open(
                    "/custom_nodes/BangtrixTranslatePro/web/translate.html",
                    "BangtrixTranslate",
                    "width=1000,height=800"
                );
            }
        });
    }
});
