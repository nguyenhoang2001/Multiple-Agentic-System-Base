const fs = require('fs');
let code = fs.readFileSync('app/agent_system/orchestrator.py', 'utf8');

const oldParse = `    except Exception:
        logger.exception("Intent extraction failed — returning empty intent")
        return UserIntent()`;

const newParse = `    except Exception as e:
        logger.warning(f"Intent extraction failed: {str(e)} — returning empty intent")
        return UserIntent()`;

code = code.replace(oldParse, newParse);

const oldParse2 = `    except Exception:
        logger.exception("Device selection failed")
        return []`;

const newParse2 = `    except Exception as e:
        logger.warning(f"Device selection failed: {str(e)}")
        return []`;

code = code.replace(oldParse2, newParse2);

fs.writeFileSync('app/agent_system/orchestrator.py', code);
