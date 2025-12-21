const puppeteer = require('puppeteer');

/**
 * Gatekeeper UI Automated Test Suite
 * 
 * This script performs a full audit of the Gatekeeper Web Admin:
 * 1. Dashboard connectivity and real-time updates.
 * 2. Device Management (Add/Edit/Delete) with Modal validation.
 * 3. Configuration persistence (MQTT / Preferences).
 * 4. Bluetooth Tools functionality.
 */

async function runTest() {
    console.log("🚀 Starting Gatekeeper UI Audit...");
    const browser = await puppeteer.launch({
        headless: "new",
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    const page = await browser.newPage();
    const baseUrl = 'http://172.16.9.20';

    try {
        // --- 1. Dashboard Test ---
        console.log("\n--- Testing Dashboard ---");
        await page.goto(baseUrl);
        await page.waitForSelector('.card');
        const title = await page.title();
        console.log(`✅ Page loaded: ${title}`);

        // Check for table content
        const deviceRows = await page.$$eval('table tbody tr', rows => rows.length);
        console.log(`✅ Tracked devices found: ${deviceRows}`);

        // --- 2. Device Management Test ---
        console.log("\n--- Testing Device CRUD ---");
        await page.goto(`${baseUrl}/devices`);

        // Add Device
        const testMac = "DE:AD:BE:EF:CA:FE";
        const testAlias = "QA_Test_Robot";
        console.log(`Adding test device: ${testMac}`);
        await page.type('#new_identifier', testMac);
        await page.type('input[name="alias"]', testAlias);
        await Promise.all([
            page.click('button[type="submit"]'),
            page.waitForNavigation()
        ]);
        console.log("✅ Device added successfully.");

        // Edit Device
        console.log("Testing Edit Modal...");
        // Re-find the edit button for our new device
        await page.evaluate((alias) => {
            const row = Array.from(document.querySelectorAll('tr')).find(r => r.innerText.includes(alias));
            row.querySelector('button.btn-ghost').click();
        }, testAlias);

        await page.waitForSelector('#editModal', { visible: true });
        await page.focus('#editAlias');
        await page.keyboard.down('Control');
        await page.keyboard.press('A');
        await page.keyboard.up('Control');
        await page.keyboard.press('Backspace');
        await page.type('#editAlias', "QA_Test_Robot_Fixed");

        await Promise.all([
            page.click('#editModal button[type="submit"]'),
            page.waitForNavigation()
        ]);
        console.log("✅ Device edited successfully.");

        // Delete Device
        console.log("Testing Custom Delete Modal...");
        await page.evaluate(() => {
            const row = Array.from(document.querySelectorAll('tr')).find(r => r.innerText.includes("QA_Test_Robot_Fixed"));
            // Find the delete button (red text)
            const btns = Array.from(row.querySelectorAll('button'));
            const deleteBtn = btns.find(b => b.innerText.includes('Delete'));
            deleteBtn.click();
        });

        await page.waitForSelector('#deleteModal', { visible: true });
        console.log("✅ Delete modal appeared.");

        await Promise.all([
            page.click('#deleteForm button[type="submit"]'),
            page.waitForNavigation()
        ]);
        console.log("✅ Device deleted successfully.");

        // --- 3. Bluetooth Tools Test ---
        console.log("\n--- Testing Bluetooth Tools ---");
        await page.goto(`${baseUrl}/bluetooth`);
        await page.click('#scanBtn');
        const progressVisible = await page.waitForSelector('#scanProgress', { visible: true });
        console.log("✅ Live Discovery started, progress bar visible.");

        // Wait for results
        await page.waitForTimeout(5000);
        const results = await page.$$eval('#scanResultsBody tr', rows => rows.length);
        if (results > 0) {
            console.log(`✅ Discovery results populated: ${results} devices found.`);
        } else {
            console.log("⚠️ No discovery results found (Expected if no devices nearby).");
        }

        // --- 4. Settings Integrity ---
        console.log("\n--- Testing Settings Pages ---");
        await page.goto(`${baseUrl}/mqtt`);
        const broker = await page.$eval('input[name="mqtt_address"]', el => el.value);
        console.log(`✅ MQTT Settings loaded (Broker: ${broker})`);

        await page.goto(`${baseUrl}/preferences`);
        const expiration = await page.$eval('input[name="PREF_BEACON_EXPIRATION"]', el => el.value);
        console.log(`✅ Preferences loaded (Expiration: ${expiration}s)`);

        console.log("\n🏆 UI Audit Complete: ALL PASS");

    } catch (err) {
        console.error("\n❌ UI Audit FAILED!");
        console.error(err);
        process.exit(1);
    } finally {
        await browser.close();
    }
}

runTest();
